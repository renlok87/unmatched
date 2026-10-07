// VS-3 HB-27 / HB-28 / HB-47: the game mode's side of DECKS and the deck panel - see UmHudDeckBlocks.h.
#include "UmHudDeckBlocks.h"

#include "UmGameHud.h"
#include "UmHudDecks.h"
#include "UmHudHand.h"

TArray<FString> FUmDeckBlocks::Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                                     const TSharedPtr<FS09HudPressArbiter>& Arbiter, FCallbacks Callbacks) {
  TArray<FString> Lines;
  if (Blocks.IsSlate(FName(TEXT("decks")))) {
    Lines.Add(TEXT("HUD-DECKS-UMG impl=slate reason=-S08SlateHud=decks"));
  } else {
    UUmHudDecks* D = CreateWidget<UUmHudDecks>(&Game, UUmHudDecks::WidgetClass());
    if (D && Game.SetBlock(EUmGameSlot::Decks, D)) {
      Decks = D;
      D->SetInput(Arbiter, MoveTemp(Callbacks.OnChip));
      D->SetVisibility(ESlateVisibility::Collapsed);  // Refresh shows it with the live match HUD
      FString Missing;
      Lines.Add(FString::Printf(TEXT("HUD-DECKS-UMG impl=umg created=1 source=%s parts=%d missing=%s"), *D->SourceName(),
                                D->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
    } else {
      Lines.Add(TEXT("HUD-DECKS-UMG impl=umg created=0 reason=create-failed"));
    }
  }
  if (Blocks.IsSlate(FName(TEXT("deckpanel")))) {
    Lines.Add(TEXT("HUD-DECKPANEL-UMG impl=slate reason=-S08SlateHud=deckpanel"));
    return Lines;
  }
  UUmHudDeckPanel* P = CreateWidget<UUmHudDeckPanel>(&Game, UUmHudDeckPanel::WidgetClass());
  if (!P || !Game.SetBlock(EUmGameSlot::DeckPanel, P)) {
    Lines.Add(TEXT("HUD-DECKPANEL-UMG impl=umg created=0 reason=create-failed"));
    return Lines;
  }
  Panel = P;
  P->SetInput(Arbiter, MoveTemp(Callbacks.Panel));
  FString Missing;
  Lines.Add(FString::Printf(TEXT("HUD-DECKPANEL-UMG impl=umg created=1 source=%s parts=%d missing=%s"), *P->SourceName(),
                            P->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
  return Lines;
}

FString FUmDeckBlocks::Refresh(const FUmDeckBlocksInput& In) {
  if (!In.Layout) return FString();
  const FUmHudLayout& L = *In.Layout;
  if (UUmHudDecks* D = Decks.Get()) {
    FUmDecksFrame F;
    F.bClassS = L.bClassS;
    F.PxPerSu = L.PxPerSu;
    F.RectSu = L.Rect(EUmHudBlock::Decks);
    F.bEnglish = !In.bRu;
    D->SetFrame(F);
    D->ApplyModel(UmHudDecks::Gather(In.bLive ? In.Own : nullptr, In.OwnSlug));
  }
  UUmHudDeckPanel* P = Panel.Get();
  if (!P) return FString();
  // a fresh open drops the filter, unless D or the discard chip opened it
  if (In.bPanelOpen && !bWasOpen) bFilter = bOpenWithFilter;
  bOpenWithFilter = false;
  bWasOpen = In.bPanelOpen;
  // the frame: the layout's rect; the bottom over a drawn hand that reaches under it (ВР-VS3-37)
  FUmDeckPanelFrame F;
  F.bClassS = L.bClassS;
  F.PxPerSu = L.PxPerSu;
  F.SlotSu = L.Rect(EUmHudBlock::DeckPanel);
  FBox2D HandSu(ForceInit);
  if (In.Hand && UmGameHudSlots::ShownByProperty(In.Hand) && In.Hand->GetRow().CardPos.Num() > 0) {
    // the resting row with its caption (the lowered hand only goes down)
    const UmHudHand::FRow& Row = In.Hand->GetRow();
    HandSu = FBox2D(FVector2D(Row.LeftSu, Row.CardTopSu - UmHudHand::CaptionSu), FVector2D(Row.RightSu, L.CanvasSu.Y));
  }
  F.BottomSu = UmHudDeckPanel::BottomOver(F.SlotSu, HandSu);
  P->SetFrame(F);
  if (!In.bPanelVisible) return FString();  // closed: the content waits for the next open
  const bool bOwn = In.Side == ES09DeckSide::Own;
  const FS09PlayerPanel* Data = bOwn ? In.Own : In.Opp;
  if (!Data) return FString();
  const FS09DeckList* List = In.Lists ? S09DeckPanel::FindList(*In.Lists, Data->PlayerId) : nullptr;
  const FS09DeckPanelModel S09 = FS09DeckPanelModel::Build(In.Side, *Data, List);
  P->ApplyModel(UmHudDeckPanel::Gather(S09, bOwn ? In.OwnHero : In.OppHero, bOwn ? In.OwnSlug : In.OppSlug, In.ListState,
                                       bFilter, In.bRu));
  return S09.TraceLine();  // the model line of DE-030 (counts only)
}

FString FUmDeckBlocks::TickPanel(float ViewAlpha, bool bOpen, double NowMs, bool bReduced, TFunctionRef<void()> RefreshOnAppear) {
  UUmHudDeckPanel* P = Panel.Get();
  if (!P) return FString();
  const float Shown = bReduced ? UmHudDeckPanel::ReducedAlpha(ViewAlpha, bOpen) : ViewAlpha;
  if (Shown > 0.0f && P->GetAlpha() <= 0.0f) RefreshOnAppear();  // the first frame of an open draws the current model
  return P->ApplyView(Shown, bOpen, NowMs);
}

void FUmDeckBlocks::CollectShotLines(TArray<FString>& Out) const {
  if (const UUmHudDecks* D = Decks.Get()) D->CollectShotLines(Out);
  if (const UUmHudDeckPanel* P = Panel.Get()) P->CollectShotLines(Out);
}

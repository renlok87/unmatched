// VS-3 HB-27 / HB-28 / HB-47 (hud.csv HB-27, HB-28, HB-47; 04-hud-spec.md §2.9, §3.3, §5.1): the game mode's side of
// DECKS and the deck panel, world-free - FUmDeckBlocks builds the two blocks into the GAME screen (unless rolled back:
// -S08SlateHud=decks | deckpanel), feeds them from the applied snapshot and the deck lists (Refresh), drives the panel's
// view each frame (TickPanel: the open 80 / close 150 ms of FS09DeckPanelView, reduced motion 100 ms - ВР-VS3-40; the
// 300 ms skeleton) and keeps the filter «Только сброс» (a fresh open drops it unless D or the discard chip asked for it).
// S08FlowGameModeUmHud.cpp only hands it the data and turns its presses into the game mode's actions (04 §5.1).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09DeckPanel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtLook.h"
#include "UmHudDeckPanel.h"
#include "UmHudLayout.h"

class UUmGameHud;
class UUmHudDecks;
class UUmHudHand;

/** One refresh: the snapshot, the lists, the open side, the layout. */
struct UNMATCHED_API FUmDeckBlocksInput {
  const FUmHudLayout* Layout = nullptr;
  /** The live match HUD (no result screen, no aborted room). */
  bool bLive = false;
  bool bRu = true;
  const FS09PlayerPanel* Own = nullptr;
  const FS09PlayerPanel* Opp = nullptr;
  FString OwnHero;
  FString OwnSlug;
  FString OppHero;
  FString OppSlug;
  const TArray<FS09DeckList>* Lists = nullptr;
  /** The state of the gameDeckLists request (Loaded also for the bench's own lists). */
  EUmDeckListState ListState = EUmDeckListState::Loading;
  bool bPanelOpen = false;
  bool bPanelVisible = false;
  ES09DeckSide Side = ES09DeckSide::Own;
  /** The UMG hand: the panel's bottom keeps over a fan that reaches under it (ВР-VS3-37). */
  const UUmHudHand* Hand = nullptr;
};

class UNMATCHED_API FUmDeckBlocks {
 public:
  struct FCallbacks {
    TFunction<void(const FS09HudPressOutcome&, bool /*bDiscard*/)> OnChip;
    UUmHudDeckPanel::FInput Panel;
  };
  /** Builds the blocks not rolled back; trace lines out (HUD-DECKS-UMG, HUD-DECKPANEL-UMG). */
  TArray<FString> Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                        const TSharedPtr<FS09HudPressArbiter>& Arbiter, FCallbacks Callbacks);
  /** Feeds the chips and the visible panel; returns the 'DECK model ...' line of the panel shown ('' when closed). */
  FString Refresh(const FUmDeckBlocksInput& In);
  /** The panel's view at NowMs (ms): the opacity of the S09 view (reduced: the 100 ms close); the HUD-LOADER line of a
   *  skeleton change. RefreshOnAppear runs first on the first drawn frame of an open (the current content). */
  FString TickPanel(float ViewAlpha, bool bOpen, double NowMs, bool bReduced, TFunctionRef<void()> RefreshOnAppear);
  void CollectShotLines(TArray<FString>& Out) const;

  // ---- the filter «Только сброс» ----
  bool GetFilter() const { return bFilter; }
  void SetFilter(bool bOn) { bFilter = bOn; }
  /** The next fresh open shows the filter on (D, the discard chip). */
  void RequestFilterOnOpen() { bOpenWithFilter = true; }

  UUmHudDecks* GetDecks() const { return Decks.Get(); }
  UUmHudDeckPanel* GetPanel() const { return Panel.Get(); }
  bool DecksOnUmg() const { return Decks.IsValid(); }
  bool PanelOnUmg() const { return Panel.IsValid(); }

 private:
  TWeakObjectPtr<UUmHudDecks> Decks;
  TWeakObjectPtr<UUmHudDeckPanel> Panel;
  bool bFilter = false;
  bool bOpenWithFilter = false;
  bool bWasOpen = false;
};

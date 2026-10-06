// VS-2 HB-18...HB-21 (docs/game-design/visual/06-tasks/hud.csv; 04-hud-spec.md §2.2, §2.3, §5.1, §5.2 step H4): the
// panels of the GAME screen - PANEL-LOC, PANEL-OPP (UUmHudPlayerPanel) and OPP-HAND (UUmHudOppHand) - as one runtime
// object the game mode feeds (04 §5.1: the new code in S08/UI, the game mode only gathers its inputs in
// S08FlowGameModeUmHud.cpp).
//
//   build    the blocks whose -S08SlateHud key is not rolled back (panels: both player panels; opphand: the backs),
//            WBP or code tree, into their UUmGameHud slots; the portraits of the panels become the game mode's
//            OwnPortrait / OpponentPortrait (the turn HUD drives the ring, tracker, heart and cross on them as before).
//            ВР-01: the opponent is top-right, diagonal to mine (04 §1.6) - the left column of two portraits is gone.
//   frame    the layout event: class L / S, px per su, the OPP-HAND width (narrowed to the room right of FIELD).
//   tick     per frame, cheap (same model = no work): name, HP of the SHOWN hero (the staging holds it to contact + 80),
//            the state (own / wait / opp / ai / fallen), the sidekicks, the opponent's hand count.
// Trace: 'HUD-PANELS loc=umg|slate opp=.. opphand=.. source=..' at the build; SHOT lines per evidence frame.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHud.h"
#include "../S08ArtLook.h"
#include "../S08BoardModel.h"
#include "UmHudOppHand.h"
#include "UmHudPlayerPanel.h"

class UUmGameHud;
class UWidget;
struct FS08TurnHudLook;

namespace UmHudPanel {
/** The side's view of the fighters: name, HP, state and the sidekicks of one player (world-free, the tests drive it).
 *  Known keeps the sidekicks seen so far (a fallen one may leave the projection, its plate stays - 04 §2.2) and the
 *  hero id (a new hero = a new game: Known starts again). */
struct UNMATCHED_API FSideMemory {
  FString HeroId;
  FString HeroName;
  int32 HeroMaxHp = 0;
  TMap<FString, FUmSidekickView> Sidekicks;
  TArray<FString> Order;
};
/** "Harpies 2" -> 2, "Merlin" -> 0. */
UNMATCHED_API int32 SidekickNumber(const FString& Label);
/** "<hero slug>/<label without its number>" ("medusa/harpies", "king-arthur/merlin"). */
UNMATCHED_API FName SidekickKey(const FString& HeroSlug, const FString& Label);
/** The model of a side from the shown fighters. IsCrossed(fighter id): the death stage's cross is down (AB-8 timing:
 *  contact + 1100); bTheirTurn / bBotActing / bGameOver pick the state of 04 §7.1. */
UNMATCHED_API FUmPlayerPanelModel Gather(EUmPanelSide Side, const FString& PlayerId, const FString& HeroName,
                                         const TArray<FS08BoardFighter>& Fighters, bool bSideTurn, bool bBotActing,
                                         bool bGameOver, TFunctionRef<bool(const FString&)> IsCrossed, FSideMemory& Memory);
}  // namespace UmHudPanel

struct UNMATCHED_API FUmPanelsTick {
  /** The live match HUD is up (the result screen's board view included - the fallen heart stays on it). */
  bool bShow = false;
  const FS09PlayerPanel* Own = nullptr;
  const FS09PlayerPanel* Opp = nullptr;
  const TArray<FS08BoardFighter>* Fighters = nullptr;
  FString OwnHeroName;
  FString OppHeroName;
  bool bViewerTurn = false;
  bool bGameOver = false;
  bool bBotActing = false;
  TFunction<bool(const FString&)> IsCrossed;
};

class UNMATCHED_API FUmPanels {
 public:
  /** Builds the blocks not rolled back. OnPress(outcome, "own" | "opp") answers a click on a panel or the backs;
   *  OnInspectHidden opens the inspector on the opponent's hidden hand. Trace lines out. */
  TArray<FString> Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks, const FS08TurnHudLook& Look,
                        const FLinearColor& OwnTeam, const FLinearColor& OppTeam,
                        const TSharedPtr<FS09HudPressArbiter>& Arbiter,
                        TFunction<void(const FS09HudPressOutcome&, const TCHAR*)> OnPress, TFunction<void()> OnInspectHidden);
  void SetFrame(bool bClassS, float PxPerSu, float OppHandWidthSu);
  void Tick(const FUmPanelsTick& T);
  void CollectShotLines(TArray<FString>& Out, TFunctionRef<FS08ScreenRect(UWidget*)> RectOf) const;

  UUmHudPlayerPanel* GetLoc() const { return Loc.Get(); }
  UUmHudPlayerPanel* GetOpp() const { return Opp.Get(); }
  UUmHudOppHand* GetOppHand() const { return OppHand.Get(); }
  bool PanelsOnUmg() const { return Loc.IsValid() && Opp.IsValid(); }

 private:
  TWeakObjectPtr<UUmHudPlayerPanel> Loc;
  TWeakObjectPtr<UUmHudPlayerPanel> Opp;
  TWeakObjectPtr<UUmHudOppHand> OppHand;
  UmHudPanel::FSideMemory OwnMemory;
  UmHudPanel::FSideMemory OppMemory;
  bool bClassS = false;
  float PxPerSu = 1.0f;
  float OppHandWidthSu = 300.0f;
  bool bShown = false;
  bool bShownKnown = false;
};

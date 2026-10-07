// VS-3 HB-30...HB-33 (hud.csv HB-30, HB-31, HB-32, HB-33; 04-hud-spec.md §2.7, §5.1, §7.1): the game mode's side of
// the combat blocks, world-free - FUmCombatBlocks builds the two edges and the centre into the GAME screen (unless rolled
// back: -S08SlateHud=combat - all three; -S08SlateHud=combatcenter - the centre only, ВР-VS3-50), turns the applied
// snapshot (metadata.combatInfo, the discard piles, the defender's draft) and the combat staging (FS09CombatStage) into
// their models every refresh / frame, and keeps the life of a combat on screen:
//   declare (CUE-008)   the attacker's card at its edge: face up on the attacker's own HUD, the back on the other (ВР-VS2-HB29-07);
//   defense window      the defender's slot shield / chosen; on the defender's HUD the timer and the two buttons; on the
//                       attacker's HUD the centre «Ждём защиту…»;
//   defense played      (CUE-009, COMBAT_RESOLVE) the slot chosen (the back + «Карта выбрана») on both HUDs;
//   reveal              both faces (the resolve window's public combatInfo, or the staging's CUE-010 when the snapshots
//                       jumped it): the attack card turns first, the defense card +120 ms (HB-32); no defense - the X stamp;
//   staging             the centre: read (nothing), effects (the fired lines; the attack card's cancelled line after its
//                       canceller, X 400 ms after it, ВР-VS3-52), slam (score + outcome), hit (from the contact);
//   leave               the staging's end: the cards fade 150 ms and fly 200 ms (the own card to the own discard chip, the
//                       opponent's to PANEL-OPP, ВР-VS3-55); a new combat cuts it - nothing of the old one stays (R-03).
// Privacy: the opponent's card face enters an edge model only from public data (the revealed combatInfo, the closing
// snapshot of the staging); before that the model carries only the combat's stable instance id (no name, no card id).
// S08FlowGameModeUmHud.cpp only collects the input and turns the presses into the game mode's commands (04 §5.1).
#pragma once

#include "CoreMinimal.h"
#include "../S08Contracts.h"
#include "../../S09/S09CombatStage.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtLook.h"
#include "UmHudCombatCenter.h"
#include "UmHudCombatEdge.h"
#include "UmHudLayout.h"

class UUmGameHud;

/** One fighter of the combat as the HUD knows it. */
struct UNMATCHED_API FUmCombatFighter {
  FString Id;
  FString Name;      // the label (Medusa, King Arthur, Merlin)
  FString OwnerId;
  int32 TeamSlot = 0;  // 0 = P1, 1 = P2
  FString DeckSlug;  // the owner's hero slug: the back and the scan key
};

/** One refresh (the applied snapshot, the command state, the staging, the clocks). */
struct UNMATCHED_API FUmCombatInput {
  const FUmHudLayout* Layout = nullptr;
  /** The live match HUD (no result screen, no lobby, no aborted room). */
  bool bLive = false;
  FString ViewerId;
  bool bRu = true;
  int64 NowMs = 0;       // the game clock of the staging (AS08FlowGameMode::NowMs)
  double NowSec = 0.0;   // FPlatformTime (the timer)
  float SpeedMul = 1.0f; // UI-ACC-013
  // ---- the open combat of the applied snapshot (phase COMBAT / COMBAT_RESOLVE with combatInfo) ----
  bool bOpen = false;
  bool bResolvePhase = false;
  int32 AppliedSeq = -1;
  FS08CombatInfo Combat;
  /** The committed cards of the viewer's projection by combatInfo's ids (a hidden placeholder stays without a face). */
  FS09CardView AttackCard;
  FS09CardView DefenseCard;
  // ---- the staging (null or inactive = none) ----
  const FS09CombatStage* Stage = nullptr;
  /** The attacker and the target of the combat shown (the staging's ids while it runs, else combatInfo's). */
  FUmCombatFighter Attacker;
  FUmCombatFighter Target;
  // ---- the own defender in the defense window ----
  FString DraftDefenseId;     // CommandUi.DefenseCardId
  bool bHasLegalDefense = true;
  FS09Reason BusyWhy;         // a command in flight (HudBusyReason)
  /** The defense window deadline on the FPlatformTime clock (<= 0: none) and its length (s). */
  double DeadlineSec = 0.0;
  float WindowSec = 30.0f;
  /** The bottom of STATUS when it shows (su), -1 otherwise (the centre keeps 8 su under it). */
  float StatusBottomSu = -1.0f;
  /** CUE-008 (04 §2.7): the declare shows only the attacker's card for this long after a new combat opens; < 0 = 600 x
   *  SpeedMul (the review sheet sets it while its animations run at speed 0). */
  float DeclareMs = -1.0f;
};

class UNMATCHED_API FUmCombatBlocks {
 public:
  struct FCallbacks {
    TFunction<void(const FS09HudPressOutcome&)> OnDefend;
    TFunction<void(const FS09HudPressOutcome&)> OnNoDefense;
    TFunction<void(const FS09CardView&)> OnInspect;
  };
  /** Builds the blocks not rolled back; trace lines out (HUD-COMBAT-UMG ...). */
  TArray<FString> Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                        const TSharedPtr<FS09HudPressArbiter>& Arbiter, FCallbacks Callbacks);
  /** Feeds the blocks; returns the trace lines of the changes (HUD-COMBAT, HUD-STAMP, HUD-TIMER). */
  TArray<FString> Refresh(const FUmCombatInput& In);
  void CollectShotLines(TArray<FString>& Out) const;

  bool EdgesOnUmg() const { return EdgeOwn.IsValid() && EdgeOpp.IsValid(); }
  bool CenterOnUmg() const { return Center.IsValid(); }
  UUmHudCombatEdge* GetEdge(EUmEdgeSide Side) const { return Side == EUmEdgeSide::Own ? EdgeOwn.Get() : EdgeOpp.Get(); }
  UUmHudCombatCenter* GetCenter() const { return Center.Get(); }
  /** The UMG edges draw the defense window now (the Slate command panel gives up its block). */
  bool DrawsDefenseWindow() const { return bDefenseWindowShown; }
  /** The combat key of the combat on screen ('' none). */
  const FString& GetKey() const { return Key; }

  // ---- world-free model building (tests drive them directly) ----
  /** The edge models (own, opp) and the centre model of one input; Key is the combat's stable key. */
  static void Gather(const FUmCombatInput& In, const FString& InKey, FUmCombatEdgeModel& OutOwn, FUmCombatEdgeModel& OutOpp,
                     FUmCombatCenterModel& OutCenter, bool bDeclaring = false);
  /** The centre's lines at NowMs: the fired lines (titles in the UI language from the revealed cards) and the attack
   *  card's cancelled line after the first defender line; OutCurrent - the highlighted one. */
  static TArray<FUmCenterLine> CenterLines(const FS09CombatStage& Stage, int64 NowMs, bool bRu, int32& OutCurrent);

 private:
  FString KeyFor(const FUmCombatInput& In);
  TWeakObjectPtr<UUmHudCombatEdge> EdgeOwn;
  TWeakObjectPtr<UUmHudCombatEdge> EdgeOpp;
  TWeakObjectPtr<UUmHudCombatCenter> Center;
  FString Key;
  FString KeyPair;        // attacker|target of the combat on screen
  bool bKeyStaged = false; // the key went on into its staging
  int32 KeyStageSeq = -1;
  int64 KeyOpenedMs = 0;   // the game clock when the open combat's key was made (the declare hold)
  bool bWasShown = false;
  bool bWasStaged = false;
  int32 StagedSeq = -1;
  bool bDefenseWindowShown = false;
  FString LastCenterLine;
};

// VS-2 HB-06 (docs/game-design/visual/06-tasks/hud.csv HB-06; 04-hud-spec.md §1.6, §4, §5.1, §5.2 step H2): the game
// mode side of the UMG HUD root - every hook of the step lives here, S08FlowGameMode*.cpp only call in (04 §5.1).
//   - BuildUmHud (end of BuildHudWidgets): UUmHudRoot (WBP_UmHudRoot or the code default tree) on the viewport in the
//     HUD layer 1, its GAME screen (UUmGameHud), input mode GameAndUI without keyboard capture (HUD-RULES П7), the
//     layout on every window / UI-scale change (UmHudScale::OnUiScaleChanged).
//   - UpdateUmHudField (end of SetupCameraForBoard): FIELD = the envelope of every board cell (centre +- radius)
//     through the K1 camera (ВР-H02); recomputed with the layout on a window / scale change.
//   - WriteUmHudShotLines (every evidence shot): 'HUD-LAYOUT ...', 'SHOT widget id=UI-SCR-GAME ...', 'HUD-STACK ...'.
//   - The H2 fixes of the blocks that are still Slate (VS-1 open items, HB-02 sheet "Что не прошло" p. 2), each
//     rolled back with its block key (-S08SlateHud=<key>) or the whole -S08SlateHud:
//       hand     the SD-26 lowering of the hand (FS09HandLower, 60 su while a cell or a target is picked) keeps 48 su
//                of the row visible (04 §2.6) - the Slate strip of text chips is ~40 su per row, so the 60 su pushed it
//                off the bottom edge in the VS-1 frames at 720p and 150 % (the shot landed in the lowered slide) -
//                UmHudHandLowerCap;
//       combat   the edge cards keep out of FIELD: scaled to the room between the screen edge and the cells
//                (FUmHudLayout::EdgeRoomSu) - UmHudWrapEdge;
//       deckpanel the right combat edge fades out under the open deck panel like the side counters (nothing shows
//                through or under it) - UmHudDeckPanelLayering;
//       sub/toast (VS-4: replaced by the UMG blocks below; the Slate line / box show only on their rollback)
//   - VS-2 HB-14...HB-16 (S08/UI/UmTopStrip.h): TOP + CONN, STATUS and the banner - built with the root, framed with
//     the layout, ticked here (turn, link, banner alpha); STATUS takes the line of AddTurnStatusLine (rollback
//     -S08SlateHud=top|status|banner).
//   - VS-2 HB-18...HB-21 (S08/UI/UmHudPanels.h): PANEL-LOC, PANEL-OPP (ВР-01 diagonal) and OPP-HAND - built with the
//     root (their portraits become OwnPortrait / OpponentPortrait), framed with the layout, fed per frame from the shown
//     fighters; a click opens the deck panel of the side (rollback -S08SlateHud=panels|opphand).
//   - VS-2 exit frames (05-production-plan §3 VS-2, opt-in -S08ExitShots with -S09Flow and -S09ShotDir): the first
//     non-initial own turn and the first non-initial opponent turn each get two frames, + 0.5 s and + 3 s after the
//     turn start - set A (own turn at rest) and set B (the opponent's turn while it thinks). At that own turn start
//     the auto plan holds 3.4 s (S09SchemeQuietUntil), so the own + 3 s frame is still the idle turn and the other
//     client's + 3 s frame still shows the opponent thinking. Files s09-exit-{own,opp}-t{0.5,3.0}.png, trace EXITSHOT.
//   - VS-2 exit-frame fixes (the frames showed the new UMG blocks over the Slate blocks that stay until VS-3 / VS-4):
//       ВР-VS2-71 PANEL-OPP and OPP-HAND fade out under the open deck panel (and the open discard browser) -
//                 UmHudDeckPanelLayering;
//       ВР-VS2-72 the Slate side panel (BROWSE DISCARD PILES / YOUR DECK / OPP DECK) lay under PANEL-OPP: without the
//                 gate layer it is collapsed while it shows only those buttons (the panels, K / Shift+K and D open the
//                 same); the open browser or inspector shows it - UmHudDeckPanelLayering (rollback -S08SlateHud=panels);
//       ВР-VS2-73 the Slate command panel starts under TOP while TOP is shown (it lay under the plate) - TickUmHud
//                 (rollback -S08SlateHud=top); ВР-VS2-75 an empty command panel is not drawn (opacity 0);
//       ВР-VS2-77 a VS-2 block shown for the first time in the shot frame has no cached geometry yet (the banner on
//                 the turn start: bbox 0 / unpainted, yet the PNG shows it): its SHOT line moves to the late block of
//                 the same file (WriteUmHudLateLines, after the capture) with the painted geometry; the early block
//                 writes 'SHOT widget-late id=<id> reason=first-frame'.
//   - VS-3 HB-24 / HB-25 (S08/UI/UmHudHand.h): HAND - built with the root (rollback -S08SlateHud=hand), framed with the
//     layout, fed by RefreshHud (RefreshUmHand: the applied snapshot + the command state) and by a flip of the SD-26
//     lowering; a card press is the old hand.<instance> action (HandleHandCardClick by the current position). The
//     Slate hand panel keeps only its lines (the rule toast, the event feed, the callout) and sits over the UMG hand
//     caption, transparent while empty (ВР-VS3-22).
//   - VS-3 HB-27 / HB-47 / HB-28 (S08/UI/UmHudDecks.h, UmHudDeckPanel.h, UmSpinner.h): DECKS and the deck panel - built
//     with the root (rollback -S08SlateHud=decks|deckpanel), fed by RefreshDeckPanel (RefreshUmDecks: the applied
//     snapshot, the deck lists, the open side, the filter), faded by TickDeckPanel (TickUmDeckPanel: the view's opacity,
//     the 300 ms skeleton). The chips open the panel (deck: «Ваша»; discard and D: «Только сброс» - the Slate discard
//     browser merged into it); the panel's tabs switch the side, its rows open the inspector (the Slate one until H13,
//     moved left of the panel while it is open, ВР-VS3-41).
//   - VS-3 HB-30...HB-33 (S08/UI/UmHudCombatBlocks.h, UmHudCombatEdge.h, UmHudCombatCenter.h): the combat edges (own
//     left, opponent right, ВР-H04) and the centre - built with the root (rollback -S08SlateHud=combat | combatcenter),
//     fed by RefreshUmCombat every frame and on RefreshHud (combatInfo, the discard piles, the defender's draft, the
//     staging); the defense window's deadline is anchored on the snapshot's server time (metadata.lastActionAt, HB-31).
//     While the UMG edge draws the defense window the Slate command panel gives up that block (not under -S09Markers);
//     the banner moves under a shown combat centre (ВР-VS3-56).
//   - VS-4 HB-35 / HB-37 (S08/UI/UmHudPending.h, UmHudSourceSlot.h): PENDING and SLOT - built with the root (rollback
//     -S08SlateHud=pending | slot), the choice fed by RefreshHud (RefreshUmPending: the command state, the presenter, the
//     snapshot's deck lists and piles for the source card) and by a cheap per-frame key (the staging, the slot hold, a
//     command in flight, the combat centre); the slot every frame from TickCardSlot (TickUmSourceSlot: FS09SourceSlot,
//     the fly from the hand's handed-off card or OPP-HAND). While the UMG choice is on, the Slate command panel draws no
//     choice / discard / ability / wait block and only the buttons of the attack draft and the resolve window (ВР-VS4-02,
//     not under -S09Markers); it moves right of a shown UMG slot (ВР-VS4-14).
//   - VS-4 HB-39...HB-41 + the HB-36 trigger (S08/UI/UmHudFeedBlocks.h, UmHudLog.h, UmToastStack.h, UmHudSubtitle.h):
//     LOG, TOAST and SUB - built with the root (rollback -S08SlateHud=log | toast | sub), placed every frame by TickUmFeed
//     (the chain of 04 §2.12 over the figures, the spaces of the K1 camera, every drawn block). The producers hook in
//     with one line each: TickOpponentView (UmHudLogTrail), ShowReason (UmHudToastReason), RefreshUi (UmHudSlateToast:
//     the Slate line keeps only the rollback / the non-keyed developer strings under -S09Markers, ВР-VS4-26),
//     HandleHudPressOutcome and the refused spaces (UmHudRefusePress / UmHudRefuseCell: badge-refuse 350 ms),
//     ApplyHandLimitHintVisibility (UmHudSyncHandLimit: the sticky rule toast), OfferVoLine / the VO stop
//     (UmHudShowSubtitle / UmHudHideSubtitle), CursorOverHud (UmHudCursorOverFeed); RefreshUmPending draws the trigger
//     toast at the stack's rect (ВР-VS4-27).
//   - VS-4 HB-43 (S08/UI/UmHudActions.h): ACTIONS - built with the root (rollback -S08SlateHud=actions: the Slate BEGIN
//     MANEUVER / END TURN buttons; under -S09Markers the Slate buttons stay for the gates too), framed with the layout,
//     fed by RefreshUmActions (RefreshHud and a per-frame key: the seq, the turn, the actions, the mode, a command in
//     flight, the combat window); a cell press is the key's command (PressUmActionKey); UI-ACC-017 key hints
//     (US08UserSettings::KeyHintsNow) also turn on the STATUS chips; the flag step 'hudendturn' presses the UMG cell.
#include "S08FlowGameMode.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudStyle.h"
#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08Contracts.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "S08TurnPortraitWidget.h"
#include "S08UserSettings.h"
#include "UI/UmActionsGallery.h"
#include "UI/UmCardGallery.h"
#include "UI/UmCardMedia.h"
#include "UI/UmCombatGallery.h"
#include "UI/UmCursor.h"
#include "UI/UmDecksGallery.h"
#include "UI/UmFeedGallery.h"
#include "UI/UmGameHud.h"
#include "UI/UmHandGallery.h"
#include "UI/UmHudActions.h"
#include "UI/UmPendingGallery.h"
#include "UI/UmHudGallery.h"
#include "UI/UmHudBanner.h"
#include "UI/UmHudCombatBlocks.h"
#include "UI/UmScreenBase.h"
#include "UI/UmScreenInspect.h"
#include "UI/UmInspectGallery.h"
#include "UI/UmHudDeckBlocks.h"
#include "UI/UmHudFeedBlocks.h"
#include "UI/UmHudHand.h"
#include "UI/UmHudLayout.h"
#include "UI/UmHudPanels.h"
#include "UI/UmHudPending.h"
#include "UI/UmHudPerf.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmHudSourceSlot.h"
#include "UI/UmHudStatusLine.h"
#include "UI/UmHudTheme.h"
#include "UI/UmHudTop.h"
#include "UI/UmText.h"
#include "UI/UmTopStrip.h"
#include "UI/UmWorldGallery.h"
#include "UI/UmZoneBadges.h"
#include "../S09/S09HudPress.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "DynamicRHI.h"
#include "RenderTimer.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Input/Events.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

/** Per-run state of the UMG HUD root (owned by the game mode through a shared pointer). */
struct FUmHudRuntime {
  S08ArtLook::FS08SlateHudBlocks Blocks;
  FUmHudLayout Layout;
  bool bLayout = false;
  FString Source;
  FDelegateHandle ScaleHandle;
  // the K1 camera of SetupCameraForBoard (FIELD is the overview's, not the zoomed view's)
  bool bCamera = false;
  FVector CamLoc = FVector::ZeroVector;
  FRotator CamRot = FRotator::ZeroRotator;
  float CamFov = 35.0f;
  FBox2D FieldPx = FBox2D(ForceInit);
  FString LastLayoutLine;
  // VS-4 HB-39...HB-41: the log, the toast stack, the subtitle (UI/UmHudFeedBlocks.h); the K1 rects of the board spaces
  // (the toasts' obstacles, recomputed with the layout); the turn of each applied seq (the log's «Х{n}»: seq -> turn
  // count, turn player); the reconnect watch of «Позиции обновлены»; the EN text of the last keyed toast (the Slate
  // line keeps only the non-keyed ones under -S09Markers); the pending toast's last rect
  FUmFeedBlocks Feed;
  TArray<FBox2D> SpaceRectsSu;
  struct FSeqTurn {
    int32 Seq = 0;
    int32 Turn = 0;
    FString Player;
  };
  TArray<FSeqTurn> SeqTurns;
  bool bStreamSeenReady = false;
  bool bReconnecting = false;
  int32 ReconnectSeq = 0;
  FString KeyedToastEn;
  FBox2D PendingToastRect = FBox2D(ForceInit);
  // the SD-26 lowering cap of the hand (traced on a change)
  float HandCapSu = -1.0f;
  // VS-2 HB-12: the board half of the software cursor (UmCursor.h)
  FUmBoardCursor BoardCursor;
  // VS-2 HB-14...HB-16: TOP + CONN, STATUS, the banner
  FUmTopStrip TopStrip;
  // VS-2 HB-18...HB-21: PANEL-LOC, PANEL-OPP, OPP-HAND
  FUmPanels Panels;
  // VS-2 exit frames (-S08ExitShots): -1 not read yet / 0 off / 1 on; turn start (Elapsed) of the first non-initial own
  // and opponent turn (-1 none yet); the frames taken (bits own 0.5, own 3.0, opp 0.5, opp 3.0)
  int32 ExitShots = -1;
  float ExitOwnAt = -1.0f;
  float ExitOppAt = -1.0f;
  uint32 ExitTaken = 0;
  // ВР-VS2-72 / -73: the Slate side panel collapsed here; the command panel's shift under TOP (su, traced on a change)
  bool bSideCollapsed = false;
  float CommandShiftSu = 0.0f;
  // ВР-VS2-77: the ids whose SHOT line waits for the late block of the current shot
  TSet<FString> LateIds;
  // VS-3 HB-24 / HB-25: the UMG hand (owned by the GAME screen's widget tree), the own hero slug last seen, the lift of
  // the Slate hand panel over the UMG hand caption (su)
  TWeakObjectPtr<UUmHudHand> Hand;
  FString HandHeroSlug;
  float SlateHandLiftSu = 0.0f;
  // VS-3 HB-27 / HB-28: DECKS and the deck panel (UI/UmHudDeckBlocks.h), the side panel's shift left of the panel
  FUmDeckBlocks DeckBlocks;
  float SideShiftSu = 0.0f;
  // VS-3 HB-30...HB-33: the combat blocks; the defense window deadline anchored on the snapshot's server time (HB-31)
  FUmCombatBlocks Combat;
  FString TimerKey;
  // VS-3 SC-01: -S08ScreenShots (-1 not read yet / 0 off / 1 on) and the UI-SCR-* id-state keys already framed
  int32 ScreenShots = -1;
  TSet<FString> ScreenShotKeys;
  // VS-3 exit frames (-S08ExitShots, sets A and C): the hover of the own exit turn; the held conditions (leaf -> since
  // when true, Elapsed) and the frames taken; the auto attack / defense holds for their frames
  float ExitHoverAt = -1.0f;
  FString ExitHoverPath;
  bool bExitHoverDone = false;
  float HoverTurnAt = -1.0f;  // the own turn the hover is tried in (-1 none), its delay after the turn start
  float HoverDelay = 3.4f;
  TMap<FString, float> ExitSince;
  TSet<FString> ExitDone;
  float ExitAttackHoldAt = -1.0f;
  float ExitAttackAskedAt = -1.0f;
  FString ExitAttackPath;
  bool bExitAttackDone = false;
  float ExitDefenseHoldAt = -1.0f;
  float ExitDefenseSince = -1.0f;
  float ExitDefenseAskedAt = -1.0f;
  FString ExitDefensePath;
  bool bExitDefenseDone = false;
  // VS-4 exit frames (HB-49): the pending head collapsed (0 idle, 1 collapsed, 2 framed, 3 expanded, 4 done); the cursor
  // steps over a hand card and a button (0 wait, 1 over the card, 2 card framed, 3 over the button, 4 button framed,
  // 5 done) on the own turn after the hover frame, through Slate's faux cursor (never the OS pointer)
  int32 ExitPendingStep = 0;
  float ExitPendingAt = -1.0f;
  FString ExitPendingPath;
  int32 ExitCursorStep = 0;
  float ExitCursorAt = -1.0f;
  float ExitCursorTurnAt = -1.0f;
  FString ExitCursorPath;
  bool bExitCursorFaux = false;
  // VS-3 HUD budget (-S08HudPerf, HUD-RULES П8): -1 not read / 0 off / 1 measuring / 2 finished
  int32 Perf = -1;
  float PerfStartAt = -1.0f;
  bool bPerfShown = true;
  FUmHudPerfMeter PerfMeter;
  double TimerDeadlineSec = 0.0;
  float TimerWindowSec = 30.0f;
  float BannerShiftSu = 0.0f;
  // VS-4 HB-35 / HB-37: the choice and the source card; the per-frame refresh key of the choice; the title of the open
  // own head (STATUS «Сделайте выбор: {card}»); the slot's card revision and where it flies from; the command panel's
  // shift right of the slot
  TWeakObjectPtr<UUmHudPending> Pending;
  TWeakObjectPtr<UUmHudSourceSlot> Slot;
  FString PendingTickKey;
  FString PendingHeadId;
  FString PendingTitle;
  uint32 SlotRevision = 0;
  FVector2D SlotFlyFrom = FVector2D::ZeroVector;
  float CommandShiftXSu = 0.0f;
  // VS-4 HB-43: ACTIONS, its per-frame refresh key; UI-ACC-017 (-1 not traced yet / 0 / 1) and the mode last traced
  TWeakObjectPtr<UUmHudActions> Actions;
  FString ActionsTickKey;
  int32 KeyHintsShown = -1;
  FString KeyHintsMode;
  // VS-4 FX-38: the zone icons at the hovered space (a viewport widget of the board layer), the last pick
  TWeakObjectPtr<UUmZoneBadges> Zones;
  FVector2D ZoneMouse = FVector2D(-1.0, -1.0);
  uint64 ZonePickFrame = 0;
  FIntPoint ZoneCell = FIntPoint(-1, -1);
  // VS-4 V4 (H13) SC-21...SC-23 / CP-22: INSPECT in the root's Modals; the key of what it shows, the deck grid side, the
  // source of the next open; CP-21: the CUE-006 show of the last flashed seq (G-CUE) and its done time (game clock)
  TWeakObjectPtr<UUmScreenInspect> Inspect;
  FString InspectKey;
  bool bInspectDeck = false;
  bool bInspectDeckOwn = true;
  TOptional<EUmInspectSource> InspectSourceNext;
  int32 FlashSeq = INDEX_NONE;
  int64 FlashStartMs = -1;
  int64 FlashDoneMs = -1;
  // VS-4 V4 evidence (-S08InspectShots): -1 not read / 0 off / 1 on; the own turn it starts at, the next step; the HB-47
  // skeleton frame (the deck panel opened while the lists load)
  int32 InspectShots = -1;
  float InspectTurnAt = -1.0f;
  int32 InspectShotStep = 0;
  float SkeletonOpenAt = -1.0f;
  float SkeletonAfter = 0.8f;
  float SkeletonFirstAt = -1.0f;
  float SkeletonDoneAt = -1.0f;
  bool bSkeletonShotDone = false;
};

namespace {
FBox2D UmHudPxToSu(const FS08ScreenRect& R, float PxPerSu) {
  const float S = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  return FBox2D(FVector2D(R.X0 / S, R.Y0 / S), FVector2D(R.X1 / S, R.Y1 / S));
}
}  // namespace

bool AS08FlowGameMode::UmHudBlockOnSlate(const TCHAR* Key) const {
  // without the runtime (before BuildUmHud) everything is the old Slate path
  return !UmHud.IsValid() || UmHud->Blocks.IsSlate(FName(Key));
}

void AS08FlowGameMode::BuildUmHud() {
  if (!UmHud.IsValid()) UmHud = MakeShared<FUmHudRuntime>();
  FUmHudRuntime& R = *UmHud;
  R.Blocks = S08ArtLook::SlateHudBlocks();
  if (!R.ScaleHandle.IsValid()) {
    R.ScaleHandle = UmHudScale::OnUiScaleChanged().AddUObject(this, &AS08FlowGameMode::HandleUmHudScaleChanged);
  }
  TArray<FString> Unknown;
  for (const FName& K : R.Blocks.Unknown) Unknown.Add(K.ToString());
  if (!R.Blocks.UmgRoot()) {
    // ВР-H15: the whole HUD as before the step - no root, no input-mode change, no layout fix
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-ROOT impl=slate reason=%s"),
                                            S08ArtLook::Enabled() ? TEXT("-S08SlateHud") : TEXT("grey-board")));
    return;
  }
  UWorld* World = GetWorld();
  UmHudRoot = UUmHudRoot::Create(World, &R.Source);
  if (!UmHudRoot) {
    ArtHud.PendingTrace.Add(TEXT("HUD-ROOT impl=umg created=0 reason=create-failed"));
    BuildTurnPortraitFallback(TEXT("umg-root-failed"));  // VS-3 (VS-2 review): the portraits never vanish
    return;
  }
  // 04 §1: the HUD layer (the Slate HUD canvas is in the same layer until its blocks move in)
  UmHudRoot->AddToViewport(1);
  UUmGameHud* Game = UmHudRoot->EnsureGameHud();
  // HUD-RULES П7: GameAndUI, the viewport keeps the keyboard (no widget to focus), the cursor stays visible
  if (APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr) {
    FInputModeGameAndUI Mode;
    Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    Mode.SetHideCursorDuringCapture(false);
    PC->SetInputMode(Mode);
  }
  FString RootMissing, GameMissing;
  const bool bRootParts = UmHudRoot->HasAllParts(&RootMissing);
  const bool bGameParts = Game && Game->HasAllParts(&GameMissing);
  ArtHud.PendingTrace.Add(FString::Printf(
      TEXT("HUD-ROOT impl=umg created=1 root=%s game=%s parts=%d/%d missing=%s layer=1 input=GameAndUI slate=%s "
           "unknown=%s cache=%d"),
      *R.Source, Game ? (Game->UsesCodeDefaultTree() ? TEXT("code-default") : *Game->GetClass()->GetPathName()) : TEXT("none"),
      bRootParts ? 1 : 0, bGameParts ? 1 : 0,
      (RootMissing + GameMissing).IsEmpty() ? TEXT("-") : *(RootMissing + TEXT(" ") + GameMissing),
      R.Blocks.Blocks.Num() ? *R.Blocks.ImplField() : TEXT("-"), Unknown.Num() ? *FString::Join(Unknown, TEXT(",")) : TEXT("-"),
      UmHudRoot->GetGameCache() ? 1 : 0));  // VS-5 E4: the invalidation box around GAME (rollback -S08HudNoCache)
  // VS-2 HB-12: the software cursors (04 §3.2); -S08SlateHud=cursor keeps the system cursor
  FString CursorSource;
  const bool bCursors = !R.Blocks.IsSlate(FName(TEXT("cursor"))) && UmHudRoot->InstallCursors(&CursorSource);
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-CURSOR installed=%d impl=%s source=%s"), bCursors ? 1 : 0,
                                          bCursors ? TEXT("software") : TEXT("system"), bCursors ? *CursorSource : TEXT("-")));
  BuildUmTopStrip();  // VS-2 HB-14...HB-16: before the layout (the STATUS slot sizes to its block)
  BuildUmPanels();    // VS-2 HB-18...HB-21
  BuildUmHand();      // VS-3 HB-24 / HB-25
  BuildUmDecks();     // VS-3 HB-27 / HB-28
  BuildUmCombat();    // VS-3 HB-30...HB-33
  BuildUmPending();   // VS-4 HB-35 / HB-37
  BuildUmFeed();      // VS-4 HB-39...HB-41
  BuildUmActions();   // VS-4 HB-43
  BuildUmInspect();   // VS-4 V4 (H13): INSPECT in the root's Modals
  RefreshUmHudLayout();
}

void AS08FlowGameMode::HandleUmHudScaleChanged(const FUmHudScaleState& /*State*/) { RefreshUmHudLayout(); }

void AS08FlowGameMode::HandleUmHudEndPlay() {
  FinishUmHudPerf(TEXT("end-play"));  // VS-3 -S08HudPerf: the summary of a match that did not end
  if (UmHud.IsValid() && UmHud->ScaleHandle.IsValid()) {
    UmHudScale::OnUiScaleChanged().Remove(UmHud->ScaleHandle);
    UmHud->ScaleHandle.Reset();
  }
  if (UmHudRoot) UmHudRoot->UninstallCursors();  // VS-2 HB-12
  if (UmHudRoot) UmHudRoot->RemoveFromParent();
}

void AS08FlowGameMode::UpdateUmHudField(const FVector& CameraLocation, const FRotator& CameraRotation, float HFovDeg) {
  if (!UmHud.IsValid()) UmHud = MakeShared<FUmHudRuntime>();
  UmHud->bCamera = true;
  UmHud->CamLoc = CameraLocation;
  UmHud->CamRot = CameraRotation;
  UmHud->CamFov = HFovDeg;
  RefreshUmHudLayout();
}

void AS08FlowGameMode::RefreshUmHudLayout() {
  if (!UmHud.IsValid() || !GEngine || !GEngine->GameViewport) return;
  FUmHudRuntime& R = *UmHud;
  FVector2D Viewport(0.0, 0.0);
  GEngine->GameViewport->GetViewportSize(Viewport);
  if (Viewport.X <= 0.0 || Viewport.Y <= 0.0) return;
  const FUmHudScaleState& Scale = UmHudScale::Current();
  float PxPerSu = Scale.Window.X > 0 ? Scale.PxPerSu() : HudPixelsPerUnit();
  if (PxPerSu <= 0.0f) PxPerSu = 1.0f;
  FBox2D FieldSu(ForceInit);
  if (R.bCamera) {
    // ВР-H02: every cell of the board, its centre +- its radius on the play plane
    TArray<FVector> Centres;
    for (int32 Y = 0; Y < BoardModel.Height; ++Y) {
      for (int32 X = 0; X < BoardModel.Width; ++X) {
        if (BoardModel.IsBoardSpace(X, Y)) Centres.Add(BoardModel.CellToWorld(X, Y));
      }
    }
    const float Radius = BoardModel.bHasTopology ? BoardModel.LayoutFrame.SpaceRadiusUU() : 0.5f * FS08BoardModel::CellSizeUU;
    UmHudField::FView View;
    View.Location = R.CamLoc;
    View.Rotation = R.CamRot;
    View.HFovDeg = R.CamFov;
    View.ViewportPx = Viewport;
    R.FieldPx = UmHudField::CellsEnvelopePx(View, Centres, Radius);
    if (R.FieldPx.bIsValid) FieldSu = FBox2D(R.FieldPx.Min / PxPerSu, R.FieldPx.Max / PxPerSu);
    // VS-4 HB-40: each space's rect (centre +- radius) - the toasts' and the subtitle's obstacles (04 §2.12)
    R.SpaceRectsSu.Reset();
    for (const FVector& C : Centres) {
      const FBox2D B = UmHudField::CellsEnvelopePx(View, {C}, Radius);
      if (B.bIsValid) R.SpaceRectsSu.Add(FBox2D(B.Min / PxPerSu, B.Max / PxPerSu));
    }
  }
  R.Layout = FUmHudLayout::Compute(Viewport / PxPerSu, PxPerSu, FieldSu.bIsValid ? &FieldSu : nullptr);
  R.Layout.bEnglishChips = UmCardMedia::PreferredLang() == TEXT("en");  // VS-3 HB-27: the chip widths of the language
  R.bLayout = true;
  if (UmHudRoot) {
    if (UUmGameHud* Game = UmHudRoot->GetGameHud()) Game->ApplyLayout(R.Layout, R.Blocks.Blocks, R.Blocks.bAll);
  }
  // VS-2 HB-14...HB-16: class, scale and the STATUS width of the top strip
  FUmTopStripFrame StripFrame;
  StripFrame.bClassS = R.Layout.bClassS;
  StripFrame.PxPerSu = R.Layout.PxPerSu;
  const FBox2D StatusRect = R.Layout.Rect(EUmHudBlock::Status);
  StripFrame.StatusMaxWidthSu = StatusRect.bIsValid ? static_cast<float>(StatusRect.Max.X - StatusRect.Min.X) : 600.0f;
  StripFrame.bKeyHints = UmKeyHintsNow();  // VS-4 HB-43: UI-ACC-017 (04 §2.11) - the STATUS chips with the ACTIONS ones
  R.TopStrip.SetFrame(StripFrame);
  const FBox2D OppHandRect = R.Layout.Rect(EUmHudBlock::OppHand);  // VS-2 HB-18...HB-21
  R.Panels.SetFrame(R.Layout.bClassS, R.Layout.PxPerSu,
                    OppHandRect.bIsValid ? static_cast<float>(OppHandRect.Max.X - OppHandRect.Min.X) : 0.0f);
  R.SlateHandLiftSu = R.Layout.HandVisibleSu + 22.0f + 8.0f;  // VS-3 HB-24 (ВР-VS3-22)
  if (UUmHudHand* Hand = R.Hand.Get()) Hand->SetFrame(FUmHandFrame::FromLayout(R.Layout, CombatSpeedMul()));
  RefreshUmDecks();  // VS-3 HB-27 / HB-28: the chips and the panel take the new rects
  RefreshUmPending();  // VS-4 HB-35: the choice takes the new frame (the slot: its next TickCardSlot)
  RefreshUmActions();  // VS-4 HB-43: the cells take the new rect and class
  const FString Line = R.Layout.TraceLine(FIntPoint(FMath::RoundToInt(Viewport.X), FMath::RoundToInt(Viewport.Y)));
  if (Line != R.LastLayoutLine) {
    R.LastLayoutLine = Line;
    if (FS08Trace::IsOpen()) {
      FS08Trace::Write(Line);
    } else {
      ArtHud.PendingTrace.Add(Line);
    }
  }
}

TSharedRef<SWidget> AS08FlowGameMode::UmHudWrapEdge(const TSharedRef<SWidget>& Edge, bool bLeft) {
  // combat: the edge card keeps out of FIELD - scaled down to the room between the screen edge and the cells (1 when
  // it fits: 1080p and 720p at 100 %; ~0.8 at 1080p 150 %). The block itself (230 / 150 su cards) is step H9.
  return SNew(SScaleBox)
      .Stretch(EStretch::UserSpecified)
      .UserSpecifiedScale(TAttribute<float>::CreateLambda([this, Edge, bLeft]() {
        if (!UmHud.IsValid() || !UmHud->bLayout || UmHudBlockOnSlate(TEXT("combat"))) return 1.0f;
        const float Width = static_cast<float>(Edge->GetDesiredSize().X);
        const float Room = UmHud->Layout.EdgeRoomSu(bLeft);
        return Width > 1.0f && Room < Width ? FMath::Max(0.5f, Room / Width) : 1.0f;
      }))[Edge];
}

float AS08FlowGameMode::UmHudHandLowerCap(float OffsetSu) const {
  // VS-3 HB-24 (ВР-VS3-22): the UMG hand goes down by itself; the Slate panel keeps only its lines and sits 8 su over
  // the UMG hand caption
  if (UmHandOnUmg()) return -UmHud->SlateHandLiftSu;
  if (OffsetSu <= 0.0f || UmHudBlockOnSlate(TEXT("hand")) || !HandBox.IsValid()) return OffsetSu;
  // 04 §2.6 (SD-26): the lowered hand keeps 48 su of its row visible. The row of the Slate hand is the strip of text
  // chips (the last child of HandBox) plus the panel padding under it (10 su, BuildHudWidgets).
  FChildren* HandChildren = HandBox->GetChildren();
  if (!HandChildren || HandChildren->Num() == 0) return OffsetSu;
  constexpr float PanelPaddingSu = 10.0f;
  constexpr float VisibleRowSu = 48.0f;
  const float Row = static_cast<float>(HandChildren->GetChildAt(HandChildren->Num() - 1)->GetDesiredSize().Y) + PanelPaddingSu;
  const float Cap = FMath::Max(0.0f, Row - VisibleRowSu);
  if (UmHud.IsValid() && !FMath::IsNearlyEqual(UmHud->HandCapSu, Cap, 0.5f)) {
    UmHud->HandCapSu = Cap;
    FS08Trace::Write(FString::Printf(TEXT("HUD-HAND lowerCap=%.0f row=%.0f visible>=%.0f (04 §2.6)"), Cap, Row, VisibleRowSu));
  }
  return FMath::Min(OffsetSu, Cap);
}

FMargin AS08FlowGameMode::UmHudToastOffset() const {
  // the old place: 150 su over the bottom edge (BuildHudWidgets). VS-4 HB-40: the Slate line shows only on its rollback
  // (-S08SlateHud=toast) and for the non-keyed developer strings under -S09Markers - at the old place, as before H2
  return FMargin(0.0f, -150.0f, 0.0f, -150.0f);
}

void AS08FlowGameMode::UmHudDeckPanelLayering(float DeckAlpha) {
  // VS-3 HB-28 (ВР-VS3-41): the Slate inspector (until H13) opens left of the UMG deck panel while that is drawn
  if (UmHud.IsValid()) {
    FUmHudRuntime& R = *UmHud;
    const UUmHudDeckPanel* Panel = R.DeckBlocks.GetPanel();
    const float Shift = Panel && DeckAlpha > 0.0f && bInspecting && !UmInspectOnUmg() ? Panel->PanelRectSu().GetSize().X + 8.0f : 0.0f;
    const TSharedPtr<SWidget> Side = ArtHud.SidePanel.Pin();
    if (Side.IsValid() && !FMath::IsNearlyEqual(Shift, R.SideShiftSu, 0.5f)) {
      R.SideShiftSu = Shift;
      Side->SetRenderTransform(Shift > 0.0f ? TOptional<FSlateRenderTransform>(FSlateRenderTransform(FVector2f(-Shift, 0.0f)))
                                            : TOptional<FSlateRenderTransform>());
    }
  }
  // ВР-VS2-71 / -72 (VS-2 exit frames): PANEL-OPP and OPP-HAND at the top right, the deck panel and the Slate side panel
  if (UmHud.IsValid() && UmHud->Panels.PanelsOnUmg()) {
    FUmHudRuntime& R = *UmHud;
    const bool bSideOpen = bDiscardBrowserOpen || (bInspecting && !UmInspectOnUmg());  // VS-4 H13: the UMG modal
    // the gate layer (-S09Markers) keeps the side panel and its debug lines as they were
    if (const TSharedPtr<SWidget> Side = S08ArtLook::S08Markers() ? nullptr : ArtHud.SidePanel.Pin()) {
      if (!bSideOpen && Side->GetVisibility() != EVisibility::Collapsed) {
        Side->SetVisibility(EVisibility::Collapsed);
        R.bSideCollapsed = true;
      } else if (bSideOpen && R.bSideCollapsed) {
        Side->SetVisibility(EVisibility::Visible);
        R.bSideCollapsed = false;
      }
    }
    // VS-3 HB-28 (ВР-VS3-42): the UMG deck panel covers no block in class L - PANEL-OPP and OPP-HAND stay; in class S
    // it lies over OPP-HAND (04 §1.6 exception), which fades with it
    const bool bUmDeck = R.DeckBlocks.PanelOnUmg();
    const float Alpha = FMath::Clamp(DeckAlpha, 0.0f, 1.0f);
    // the Slate side panel (inspector, browser) at the top right lies under them - unless it moved left of the deck panel
    const float SideCover = bSideOpen && R.SideShiftSu <= 0.0f ? 1.0f : 0.0f;
    const float KeepOpp = 1.0f - FMath::Max(SideCover, bUmDeck ? 0.0f : Alpha);
    const float KeepHand = 1.0f - FMath::Max(SideCover, bUmDeck ? (R.Layout.bClassS ? Alpha : 0.0f) : Alpha);
    UWidget* Fading[2] = {R.Panels.GetOpp(), R.Panels.GetOppHand()};
    for (int32 I = 0; I < 2; ++I) {
      const float Keep = I == 0 ? KeepOpp : KeepHand;
      if (Fading[I] && !FMath::IsNearlyEqual(Fading[I]->GetRenderOpacity(), Keep, 1.0e-3f)) Fading[I]->SetRenderOpacity(Keep);
    }
  }
  // deckpanel: what lies under the open deck panel at the right edge fades out with it (the side counters already
  // do): the right combat edge - a read-only panel never shows a block through it or under its short bottom edge
  if (UmHud.IsValid() && !UmHudBlockOnSlate(TEXT("deckpanel"))) {
    // VS-3 HB-30: the UMG right edge fades under the open deck panel the same way
    if (UUmHudCombatEdge* Edge = UmHud->Combat.GetEdge(EUmEdgeSide::Opp)) {
      if (!FMath::IsNearlyEqual(Edge->GetRenderOpacity(), 1.0f - DeckAlpha, 1.0e-3f)) Edge->SetRenderOpacity(1.0f - DeckAlpha);
    }
  }
  if (!CombatEdgeRight.IsValid() || UmHudBlockOnSlate(TEXT("deckpanel"))) return;
  CombatEdgeRight->SetRenderOpacity(1.0f - DeckAlpha);
  const EVisibility Want = DeckAlpha > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Visible;
  if (CombatEdgeRight->GetVisibility() != Want) CombatEdgeRight->SetVisibility(Want);
}

void AS08FlowGameMode::WriteUmHudLateLines() {
  // ВР-VS2-77: inside 'SHOT late begin/end' of the file - the deferred blocks with the geometry painted this frame
  if (!UmHud.IsValid()) return;
  FUmHudRuntime& R = *UmHud;
  // ВР-VS3-72: what the hand and the combat edges paint in the captured frame (the card art the pixel gates mask; the
  // early block is written at the request, a card can start a flight before the capture)
  {
    const float Px = R.Layout.PxPerSu > 0.0f ? R.Layout.PxPerSu : 1.0f;
    auto Fmt = [Px](const FBox2D& B) {
      return FString::Printf(TEXT("(%.0f,%.0f,%.0f,%.0f)"), B.Min.X * Px, B.Min.Y * Px, B.Max.X * Px, B.Max.Y * Px);
    };
    if (const UUmHudHand* Hand = R.Hand.Get()) {
      TArray<FBox2D> Rects;
      if (UmGameHudSlots::ShownByProperty(Hand)) Hand->PaintedCardRectsSu(Rects);
      TArray<FString> Parts;
      for (const FBox2D& B : Rects) Parts.Add(Fmt(B));
      if (Parts.Num()) FS08Trace::Write(TEXT("HUD-PAINT-LATE id=UI-HUD-HAND rects=") + FString::Join(Parts, TEXT(";")));
    }
    for (const EUmEdgeSide Side : {EUmEdgeSide::Own, EUmEdgeSide::Opp}) {
      const UUmHudCombatEdge* Edge = R.Combat.GetEdge(Side);
      const FBox2D B = Edge && (Edge->IsLeaving() || UmGameHudSlots::ShownByProperty(Edge)) ? Edge->PaintedRectSu() : FBox2D(ForceInit);
      if (B.bIsValid) {
        FS08Trace::Write(FString::Printf(TEXT("HUD-PAINT-LATE id=UI-HUD-COMBAT-EDGE side=%s rects=%s"),
                                         Side == EUmEdgeSide::Own ? TEXT("own") : TEXT("opp"), *Fmt(B)));
      }
    }
  }
  if (R.LateIds.Num() == 0) return;
  TArray<FString> Lines;
  auto RectOf = [this](UWidget* W) {
    FS08ScreenRect Rect;
    if (W) WidgetViewportRect(W->GetCachedWidget(), Rect);
    return Rect;
  };
  R.TopStrip.CollectShotLines(Lines, RectOf);
  R.Panels.CollectShotLines(Lines, RectOf);
  for (const FString& L : Lines) {
    FString Id;
    if (FParse::Value(*L, TEXT("id="), Id) && R.LateIds.Contains(Id)) FS08Trace::Write(L);
  }
  R.LateIds.Reset();
}

bool AS08FlowGameMode::UmExitShotsOn() {
  if (!UmHud.IsValid() || !bAutoS09 || S09ShotDir.IsEmpty()) return false;
  FUmHudRuntime& R = *UmHud;
  if (R.ExitShots < 0) R.ExitShots = FParse::Param(FCommandLine::Get(), TEXT("S08ExitShots")) ? 1 : 0;
  return R.ExitShots == 1;
}

void AS08FlowGameMode::NoteUmExitShotsTurn(bool bOwn, bool bInitial, bool bGameOver) {
  NoteUmInspectShotsTurn(bOwn, bInitial, bGameOver);  // VS-4 V4 evidence (-S08InspectShots)
  if (bInitial || bGameOver || !UmExitShotsOn()) return;
  FUmHudRuntime& R = *UmHud;
  // VS-4 HB-12 cursor frames: the first own turn after the hover frame, its auto plan held 4.5 s for them
  if (bOwn && R.bExitHoverDone && R.ExitCursorStep == 0 && R.ExitCursorTurnAt < 0.0f) {
    R.ExitCursorTurnAt = Elapsed;
    S09SchemeQuietUntil = FMath::Max(S09SchemeQuietUntil, Elapsed + 4.5f);
    FS08Trace::Write(FString::Printf(TEXT("EXITSHOT cursor turn seq=%d at=%.2f hold=4.5"),
                                     Flow.IsValid() ? Flow->GetAppliedSnapshot().SequenceNumber : -1, Elapsed));
  }
  float& At = bOwn ? R.ExitOwnAt : R.ExitOppAt;
  // VS-3 set A hover (ВР-VS3-73): tried at the first own turn + 3.4 s; a turn whose start still shows the last combat
  // (or a choice) passes it on to the next own turn, which holds its auto plan 2.6 s for it
  if (bOwn && !R.bExitHoverDone && R.ExitHoverAt < 0.0f) {
    R.HoverTurnAt = Elapsed;
    R.HoverDelay = At >= 0.0f ? 1.0f : 3.4f;
    if (At >= 0.0f) {
      S09SchemeQuietUntil = FMath::Max(S09SchemeQuietUntil, Elapsed + 2.6f);
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT hover turn seq=%d at=%.2f hold=2.6"),
                                       Flow.IsValid() ? Flow->GetAppliedSnapshot().SequenceNumber : -1, Elapsed));
    }
  }
  if (At >= 0.0f) return;  // only the first turn of each side
  At = Elapsed;
  // the own turn stays at rest past its + 3 s frame and the VS-3 hover frame (+ 3.4 s hover, + 3.9 s frame); the other
  // client sees the opponent thinking as long
  if (bOwn) S09SchemeQuietUntil = FMath::Max(S09SchemeQuietUntil, Elapsed + 5.0f);
  FS08Trace::Write(FString::Printf(TEXT("EXITSHOT turn=%s seq=%d at=%.2f hold=%s"), bOwn ? TEXT("own") : TEXT("opp"),
                                   Flow.IsValid() ? Flow->GetAppliedSnapshot().SequenceNumber : -1, Elapsed,
                                   bOwn ? TEXT("5.0") : TEXT("0")));
}

void AS08FlowGameMode::TickUmExitShots() {
  if (!UmExitShotsOn()) return;
  FUmHudRuntime& R = *UmHud;
  struct FPlanned {
    bool bOwn;
    float Dt;
    const TCHAR* Leaf;
  };
  static const FPlanned Plan[] = {{true, 0.5f, TEXT("s09-exit-own-t0.5.png")},
                                  {true, 3.0f, TEXT("s09-exit-own-t3.0.png")},
                                  {false, 0.5f, TEXT("s09-exit-opp-t0.5.png")},
                                  {false, 3.0f, TEXT("s09-exit-opp-t3.0.png")}};
  for (int32 I = 0; I < UE_ARRAY_COUNT(Plan); ++I) {
    const float At = Plan[I].bOwn ? R.ExitOwnAt : R.ExitOppAt;
    if ((R.ExitTaken & (1u << I)) || At < 0.0f || Elapsed < At + Plan[I].Dt) continue;
    if (Hud.bValid && (Hud.bGameOver || Hud.bViewerTurn != Plan[I].bOwn)) {  // VS-5 E4: the turn passed (or the match)
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT skip %s turn-changed dt=%.2f"), Plan[I].Leaf, Elapsed - At));
      (Plan[I].bOwn ? R.ExitOwnAt : R.ExitOppAt) = -1.0f;
      continue;
    }
    R.ExitTaken |= 1u << I;
    FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot %s dt=%.2f"), Plan[I].Leaf, Elapsed - At));
    TakeEvidenceShot(S09ShotDir / Plan[I].Leaf);  // the evidence queue orders it after a shot in flight
    return;
  }
  TickUmExitShotsVs3();
}

// ------------------------------------------------------------------------------------------------ VS-3 exit frames
// 05-production-plan §3 VS-3 (opt-in -S08ExitShots with -S09Flow and -S09ShotDir, ВР-VS3-68...): set A - the hover of
// a hand card at the own exit turn, the attack selected (the auto attack's draft held for its frame), the hand of 3 / 7
// / 9 cards; set C - the defense window on both clients (the defender's window held for its frame, the attacker's
// «Ждём защиту…»), the reveal, the no-defense stamp, the last 10 s of the timer. Files s09-exit-*.png (published by
// run-combat-demo with the VS-2 ones), trace 'EXITSHOT ...' with the states the frame shows (no card names).

namespace {
const TCHAR* UmExitEdgeState(const UUmHudCombatEdge* E) {
  return E && E->GetModel().bShow ? UmHudCombatEdge::StateName(E->GetModel().State) : TEXT("-");
}
}  // namespace

void AS08FlowGameMode::TickUmExitShotsVs3() {
  FUmHudRuntime& R = *UmHud;
  if (!Hud.bValid || Hud.bGameOver || IsResultScreenShown()) return;
  UUmHudHand* Hand = R.Hand.Get();
  const bool bHandShown = Hand && Hand->GetModel().bShow;
  const int32 HandN = bHandShown ? Hand->GetModel().RowCount() : -1;
  const FString HandState = bHandShown ? Hand->StateName() : FString(TEXT("-"));
  const UUmHudCombatEdge* EOwn = R.Combat.GetEdge(EUmEdgeSide::Own);
  const UUmHudCombatEdge* EOpp = R.Combat.GetEdge(EUmEdgeSide::Opp);
  const UUmHudCombatCenter* Center = R.Combat.GetCenter();
  const FString States = FString::Printf(
      TEXT("hand=%d/%s edges=%s/%s center=%s turn=%s seq=%d"), HandN, *HandState, UmExitEdgeState(EOwn),
      UmExitEdgeState(EOpp),
      Center && UmGameHudSlots::ShownByProperty(Center) ? UmHudCombatCenter::StateName(Center->GetModel().State) : TEXT("-"),
      Hud.bViewerTurn ? TEXT("own") : TEXT("opp"), Hud.SequenceNumber);
  // ---- set A: the hover (ВР-VS3-73): an own turn + 3.4 s (the first) / + 1.0 s (a later one), the middle card of the
  // resting row with no combat on screen, its frame + 0.5 s ----
  const bool bEdgesShown = (EOwn && EOwn->GetModel().bShow) || (EOpp && EOpp->GetModel().bShow);
  if (!R.bExitHoverDone && R.HoverTurnAt >= 0.0f && Hand) {
    if (R.ExitHoverAt < 0.0f) {
      if (Elapsed >= R.HoverTurnAt + R.HoverDelay) {
        TArray<int32> Rows;
        for (int32 I = 0; I < Hand->GetModel().Cards.Num(); ++I) {
          if (Hand->RestRectSu(I).bIsValid) Rows.Add(I);
        }
        const bool bReady = Rows.Num() > 0 && HandState == TEXT("rest") && !bEdgesShown && Hud.bViewerTurn;
        if (!bReady) {
          // wait up to 1 s in this turn, then leave it to the next own turn
          if (Elapsed >= R.HoverTurnAt + R.HoverDelay + 1.0f) {
            R.HoverTurnAt = -1.0f;
            FS08Trace::Write(FString::Printf(TEXT("EXITSHOT hover postponed %s"), *States));
          }
        } else {
          // the pointer's path: a point in the middle card's strip of the resting row (HoverAtSu, 04 §2.6)
          const int32 Pick = Rows[Rows.Num() / 2];
          Hand->HoverAtSu(Hand->RestRectSu(Pick).GetCenter());
          if (Hand->GetHoverIndex() != Pick) Hand->SetHoverIndex(Pick);
          R.ExitHoverAt = Elapsed;
          FS08Trace::Write(FString::Printf(TEXT("EXITSHOT hover card=%d of %d"), Rows.IndexOfByKey(Pick), Rows.Num()));
        }
      }
    } else if (R.ExitHoverPath.IsEmpty()) {
      if (Elapsed >= R.ExitHoverAt + 0.5f && !IsEvidenceCaptureBusy()) {
        R.ExitHoverPath = S09ShotDir / TEXT("s09-exit-hand-hover.png");
        FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot s09-exit-hand-hover.png %s"), *States));
        TakeEvidenceShot(R.ExitHoverPath);
        return;
      }
    } else if (FPaths::FileExists(R.ExitHoverPath) || Elapsed >= R.ExitHoverAt + 3.0f) {
      Hand->ClearHover();
      R.bExitHoverDone = true;
      FS08Trace::Write(TEXT("EXITSHOT hover cleared"));
    }
  }
  // ---- the held conditions: a frame once the state has held long enough (its animations landed) ----
  const auto Open = [](const UUmHudCombatEdge* E) {
    const EUmEdgeState S = E && E->GetModel().bShow ? E->GetModel().State : EUmEdgeState::Hidden;
    return S == EUmEdgeState::Back || S == EUmEdgeState::Shield || S == EUmEdgeState::Chosen;
  };
  const auto Is = [](const UUmHudCombatEdge* E, EUmEdgeState S) { return E && E->GetModel().bShow && E->GetModel().State == S; };
  const bool bReveal = (Is(EOwn, EUmEdgeState::Reveal) || Is(EOpp, EUmEdgeState::Reveal)) && !Open(EOwn) && !Open(EOpp);
  const bool bWait = Center && UmGameHudSlots::ShownByProperty(Center) && Center->GetModel().State == EUmCenterState::Wait;
  // the hand frames of set A show the turn, not a combat (ВР-VS3-70): no edge on screen for 3 and 7
  const bool bCombatShown = bEdgesShown;
  struct FCond {
    const TCHAR* Leaf;
    bool bNow;
    float HoldSec;
  };
  const FCond Conds[] = {
      {TEXT("s09-exit-hand-n3.png"), HandN == 3 && HandState == TEXT("rest") && !bCombatShown, 0.8f},
      {TEXT("s09-exit-hand-n7.png"), HandN == 7 && HandState == TEXT("rest") && !bCombatShown, 0.8f},
      {TEXT("s09-exit-hand-n9.png"), HandN == 9 && (HandState == TEXT("rest") || HandState == TEXT("discard")), 0.6f},
      {TEXT("s09-exit-defense-wait.png"), bWait, 0.8f},
      {TEXT("s09-exit-defense-warn.png"), Is(EOwn, EUmEdgeState::Shield) && EOwn->GetTimerState() == EUmTimerState::Warning, 0.6f},
      {TEXT("s09-exit-reveal.png"), bReveal, 0.9f},
      {TEXT("s09-exit-nodefense.png"), Is(EOwn, EUmEdgeState::NoDefense) || Is(EOpp, EUmEdgeState::NoDefense), 0.6f},
  };
  for (const FCond& C : Conds) {
    const FString Leaf(C.Leaf);
    if (R.ExitDone.Contains(Leaf)) continue;
    if (!C.bNow) {
      R.ExitSince.Remove(Leaf);
      continue;
    }
    const float* Since = R.ExitSince.Find(Leaf);
    if (!Since) {
      R.ExitSince.Add(Leaf, Elapsed);
      continue;
    }
    if (Elapsed - *Since < C.HoldSec || IsEvidenceCaptureBusy()) continue;
    R.ExitDone.Add(Leaf);
    FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot %s held=%.2f %s"), C.Leaf, Elapsed - *Since, *States));
    TakeEvidenceShot(S09ShotDir / Leaf);
    return;  // one request per frame
  }
  TickUmExitShotsVs4();
}

// ------------------------------------------------------------------------------------------------ VS-4 exit frames
// HB-49 (04 §7.2 set D) and the VS-2 leftovers of 05 §3 VS-4: the own pending head collapsed (HoldUmExitPending, from
// the auto answer), the software cursor of HB-12 over a hand card and over the end-turn button (Slate's faux cursor:
// the OS pointer never moves), the link badge of HB-14 in syncing / lost (a slow command, a dropped stream - see
// tools/s10/delay-graphql-query-proxy.cjs), the turn banner under a shown combat centre (ВР-VS3-56). Files
// s09-exit-*.png, trace 'EXITSHOT ...'.

namespace {
/** Moves Slate's cursor user to the centre of W (absolute desktop space) as a synthetic pointer move. */
bool UmExitPointAt(const UWidget* W, FVector2D& OutAbs) {
  if (!W || !FSlateApplication::IsInitialized()) return false;
  const TSharedPtr<SWidget> Slate = W->GetCachedWidget();
  if (!Slate.IsValid() || Slate->GetCachedGeometry().GetLocalSize().IsNearlyZero()) return false;
  const FGeometry& Geo = Slate->GetCachedGeometry();
  OutAbs = FVector2D(Geo.GetAbsolutePositionAtCoordinates(FVector2f(0.5f, 0.5f)));
  FSlateApplication& App = FSlateApplication::Get();
  const TSharedPtr<FSlateUser> User = App.GetCursorUser();
  if (!User.IsValid()) return false;
  const FVector2D Last = FVector2D(User->GetCursorPosition());
  User->SetCursorPosition(OutAbs);
  App.ProcessMouseMoveEvent(FPointerEvent(App.GetUserIndexForMouse(), FSlateApplication::CursorPointerIndex,
                                          FVector2f(OutAbs), FVector2f(Last), TSet<FKey>(), EKeys::Invalid, 0.0f,
                                          FModifierKeysState()),
                            false);
  App.QueryCursor();
  return true;
}
}  // namespace

bool AS08FlowGameMode::HoldUmExitPending() {
  // set D «свёрнуто»: the first own head shown as a compact / modal UMG window - collapse (as the key C), frame,
  // expand, then the auto answer goes on
  if (!UmExitShotsOn() || !UmPendingOwnsCommandPanel()) return false;
  FUmHudRuntime& R = *UmHud;
  if (R.ExitPendingStep >= 4) return false;
  const UUmHudPending* Pending = R.Pending.Get();
  const EUmPendingView View = Pending ? Pending->GetModel().View : EUmPendingView::Hidden;
  switch (R.ExitPendingStep) {
    case 0:
      if (View != EUmPendingView::Compact && View != EUmPendingView::Modal) return false;
      TogglePendingCollapseCommand();
      R.ExitPendingStep = 1;
      R.ExitPendingAt = Elapsed;
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT pending collapse from=%s seq=%d"), UmHudPending::ViewName(View),
                                       Hud.SequenceNumber));
      return true;
    case 1:
      if (Elapsed < R.ExitPendingAt + 0.6f || IsEvidenceCaptureBusy()) {
        if (Elapsed < R.ExitPendingAt + 6.0f) return true;
      }
      R.ExitPendingPath = S09ShotDir / TEXT("s09-exit-pending-collapsed.png");
      R.ExitPendingAt = Elapsed;
      R.ExitPendingStep = 2;
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot s09-exit-pending-collapsed.png view=%s seq=%d"),
                                       UmHudPending::ViewName(View), Hud.SequenceNumber));
      TakeEvidenceShot(R.ExitPendingPath);
      return true;
    case 2:
      if (!FPaths::FileExists(R.ExitPendingPath) && Elapsed < R.ExitPendingAt + 4.0f) return true;
      if (View == EUmPendingView::Collapsed) TogglePendingCollapseCommand();
      R.ExitPendingStep = 3;
      R.ExitPendingAt = Elapsed;
      return true;
    default:
      if (Elapsed < R.ExitPendingAt + 0.4f) return true;
      R.ExitPendingStep = 4;
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT release pending view=%s"), UmHudPending::ViewName(View)));
      return false;
  }
}

void AS08FlowGameMode::TickUmExitShotsVs4() {
  FUmHudRuntime& R = *UmHud;
  // ---- HB-12 cursor: a hand card (pointer) and the end-turn button (pointer / denied) ----
  if (R.ExitCursorTurnAt >= 0.0f && R.ExitCursorStep < 5 && FSlateApplication::IsInitialized()) {
    UUmHudHand* Hand = R.Hand.Get();
    const UUmHudActions* Actions = R.Actions.Get();
    const auto Restore = [&R]() {
      if (R.bExitCursorFaux) FSlateApplication::Get().UsePlatformCursorForCursorUser(true);
      R.bExitCursorFaux = false;
    };
    const auto Line = [this]() {
      APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
      return UmHudRoot ? UmHudRoot->CursorShotLine(PC ? PC->CurrentMouseCursor.GetValue() : EMouseCursor::Default)
                       : FString(TEXT("-"));
    };
    if (R.ExitCursorStep == 0 || R.ExitCursorStep == 2) {
      const bool bFirst = R.ExitCursorStep == 0;
      if (bFirst && Elapsed < R.ExitCursorTurnAt + 1.0f) return;
      if (!bFirst && !FPaths::FileExists(R.ExitCursorPath) && Elapsed < R.ExitCursorAt + 4.0f) return;
      const UWidget* Target = nullptr;
      if (bFirst && Hand && Hud.bViewerTurn && Hand->GetModel().bShow && Hand->StateName() == TEXT("rest")) {
        const TArray<FUmHandCardModel>& Cards = Hand->GetModel().Cards;
        if (Cards.Num() > 0) Target = Hand->FindCard(Cards[Cards.Num() / 2].Card.InstanceId);
      } else if (!bFirst && Actions) {
        Target = Actions->GetButton(EUmActionKey::EndTurn);
      }
      if (!R.bExitCursorFaux) {
        FSlateApplication::Get().UsePlatformCursorForCursorUser(false);  // Slate's faux cursor: the OS pointer stays
        R.bExitCursorFaux = true;
      }
      FVector2D Abs;
      if (!UmExitPointAt(Target, Abs)) {
        if (Elapsed < R.ExitCursorTurnAt + 3.0f) return;
        FS08Trace::Write(FString::Printf(TEXT("EXITSHOT cursor %s target missing - skipped"), bFirst ? TEXT("card") : TEXT("button")));
        Restore();
        R.ExitCursorStep = 5;
        return;
      }
      R.ExitCursorStep = bFirst ? 1 : 3;
      R.ExitCursorAt = Elapsed;
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT cursor at=%s abs=(%.0f,%.0f)"), bFirst ? TEXT("card") : TEXT("button"),
                                       Abs.X, Abs.Y));
      return;
    }
    if (R.ExitCursorStep == 1 || R.ExitCursorStep == 3) {
      if (Elapsed < R.ExitCursorAt + 0.5f || IsEvidenceCaptureBusy()) return;
      const TCHAR* Leaf = R.ExitCursorStep == 1 ? TEXT("s09-exit-cursor-card.png") : TEXT("s09-exit-cursor-button.png");
      R.ExitCursorPath = S09ShotDir / Leaf;
      R.ExitCursorAt = Elapsed;
      ++R.ExitCursorStep;
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot %s %s"), Leaf, *Line()));
      TakeEvidenceShot(R.ExitCursorPath);
      return;
    }
    if (R.ExitCursorStep == 4 && (FPaths::FileExists(R.ExitCursorPath) || Elapsed >= R.ExitCursorAt + 4.0f)) {
      Restore();
      R.ExitCursorStep = 5;
      FS08Trace::Write(TEXT("EXITSHOT cursor done"));
    }
  }
  if (!Hud.bValid || Hud.bGameOver || IsResultScreenShown() || !Flow.IsValid()) return;
  // ---- HB-14 link states and the banner under the combat centre: held conditions ----
  const EUmConnState Conn = R.TopStrip.GetConn();
  const UUmHudBanner* Banner = R.TopStrip.GetBanner();
  const UUmHudCombatCenter* Center = R.Combat.GetCenter();
  const bool bCenter = Center && UmGameHudSlots::ShownByProperty(Center);
  struct FCond {
    const TCHAR* Leaf;
    bool bNow;
    float HoldSec;
  };
  const FCond Conds[] = {
      {TEXT("s09-exit-conn-syncing.png"), Conn == EUmConnState::Syncing, 0.1f},  // VS-5 E4: the match start's subscription
      {TEXT("s09-exit-conn-lost.png"), Conn == EUmConnState::Lost && Flow->GetAppliedSnapshot().SequenceNumber > 0, 0.1f},
      {TEXT("s09-exit-banner-combat.png"), Banner && Banner->GetAlpha() > 0.9f && bCenter && R.BannerShiftSu > 0.0f, 0.1f},
  };
  for (const FCond& C : Conds) {
    const FString Leaf(C.Leaf);
    if (R.ExitDone.Contains(Leaf)) continue;
    if (!C.bNow) {
      R.ExitSince.Remove(Leaf);
      continue;
    }
    const float* Since = R.ExitSince.Find(Leaf);
    if (!Since) {
      R.ExitSince.Add(Leaf, Elapsed);
      continue;
    }
    if (Elapsed - *Since < C.HoldSec || IsEvidenceCaptureBusy()) continue;
    R.ExitDone.Add(Leaf);
    FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot %s held=%.2f conn=%s bannerShift=%.0f seq=%d"), C.Leaf,
                                     Elapsed - *Since, UmConnection::StateName(Conn), R.BannerShiftSu, Hud.SequenceNumber));
    TakeEvidenceShot(S09ShotDir / Leaf);
    return;
  }
}

bool AS08FlowGameMode::HoldUmExitAttack() {
  // set A «выбрана атака»: the auto attack's complete draft (attacker, target, card - the card raised in the hand) stays
  // until its frame is written; ResumeUmExitAttack sends it (the first own attack of the run only)
  if (!UmExitShotsOn() || UmHud->bExitAttackDone) return false;
  FUmHudRuntime& R = *UmHud;
  if (R.ExitAttackHoldAt < 0.0f) {
    R.ExitAttackHoldAt = Elapsed;
    FS08Trace::Write(FString::Printf(TEXT("EXITSHOT hold attack seq=%d"), Hud.SequenceNumber));
    RefreshHud();  // the hand shows the selected attack card
  }
  return true;
}

void AS08FlowGameMode::ResumeUmExitAttack() {
  if (!UmHud.IsValid() || UmHud->ExitAttackHoldAt < 0.0f || UmHud->bExitAttackDone) return;
  FUmHudRuntime& R = *UmHud;
  if (R.ExitAttackPath.IsEmpty()) {
    if (Elapsed < R.ExitAttackHoldAt + 0.6f || IsEvidenceCaptureBusy()) {
      if (Elapsed < R.ExitAttackHoldAt + 8.0f) return;
    } else {
      R.ExitAttackPath = S09ShotDir / TEXT("s09-exit-attack-selected.png");
      R.ExitAttackAskedAt = Elapsed;
      const UUmHudHand* Hand = R.Hand.Get();
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot s09-exit-attack-selected.png hand=%s seq=%d"),
                                       Hand ? *Hand->StateName() : TEXT("-"), Hud.SequenceNumber));
      TakeEvidenceShot(R.ExitAttackPath);
      return;
    }
  } else if (!FPaths::FileExists(R.ExitAttackPath) && Elapsed < R.ExitAttackAskedAt + 6.0f) {
    return;
  }
  R.bExitAttackDone = true;
  FS08Trace::Write(FString::Printf(TEXT("EXITSHOT release attack written=%d"),
                                   !R.ExitAttackPath.IsEmpty() && FPaths::FileExists(R.ExitAttackPath) ? 1 : 0));
  if (!ConfirmCombat()) {
    // as the auto attack itself: the gate closed meanwhile - back out of the draft, retry later
    CommandUi.Mode = ES09CommandMode::None;
    CommandUi.AttackAttackerId.Reset();
    CommandUi.AttackTargetId.Reset();
    CommandUi.AttackCardId.Reset();
    NextCommandAt = Elapsed + 1.0f;
  }
}

bool AS08FlowGameMode::HoldUmExitDefense() {
  // set C «окно защиты»: the defender's first window stays open (slot «Карта не выбрана», the timer, the two buttons)
  // until its frame is written - also the attacker's «Ждём защиту…» holds as long
  if (!UmExitShotsOn() || UmHud->bExitDefenseDone) return false;
  FUmHudRuntime& R = *UmHud;
  if (R.ExitDefenseHoldAt < 0.0f) {
    R.ExitDefenseHoldAt = Elapsed;
    FS08Trace::Write(FString::Printf(TEXT("EXITSHOT hold defense seq=%d"), Hud.SequenceNumber));
  }
  if (R.ExitDefensePath.IsEmpty()) {
    // the UMG window is drawn after the 600 ms declare (ВР-VS3-59); the Slate rollback draws its block at once
    const UUmHudCombatEdge* Own = R.Combat.GetEdge(EUmEdgeSide::Own);
    const bool bWindow = !UmCombatOnUmg() || (Own && Own->GetModel().bShow && Own->GetModel().State == EUmEdgeState::Shield &&
                                              Own->GetTimerState() != EUmTimerState::Off);
    if (!bWindow) {
      R.ExitDefenseSince = -1.0f;
    } else if (R.ExitDefenseSince < 0.0f) {
      R.ExitDefenseSince = Elapsed;
    }
    if (R.ExitDefenseSince >= 0.0f && Elapsed >= R.ExitDefenseSince + 0.8f && !IsEvidenceCaptureBusy()) {
      R.ExitDefensePath = S09ShotDir / TEXT("s09-exit-defense-window.png");
      R.ExitDefenseAskedAt = Elapsed;
      FS08Trace::Write(FString::Printf(TEXT("EXITSHOT shot s09-exit-defense-window.png edge=%s timer=%s seq=%d"),
                                       UmExitEdgeState(Own),
                                       Own ? UmHudCombatEdge::TimerStateName(Own->GetTimerState()) : TEXT("-"),
                                       Hud.SequenceNumber));
      TakeEvidenceShot(R.ExitDefensePath);
      return true;
    }
    if (Elapsed < R.ExitDefenseHoldAt + 6.0f) return true;
    FS08Trace::Write(TEXT("EXITSHOT defense window never drawn - released WITHOUT the frame"));
    R.bExitDefenseDone = true;
    return false;
  }
  if (!FPaths::FileExists(R.ExitDefensePath) && Elapsed < R.ExitDefenseAskedAt + 4.0f) return true;
  R.bExitDefenseDone = true;
  FS08Trace::Write(TEXT("EXITSHOT release defense"));
  return false;
}

// ------------------------------------------------------------------------------------------------ VS-3 HUD budget

void AS08FlowGameMode::TickUmHudPerf() {
  // HUD-RULES П8 (opt-in -S08HudPerf, UI/UmHudPerf.h): the UMG HUD root collapsed / shown in alternating blocks
  if (!UmHud.IsValid() || !UmHudRoot) return;
  FUmHudRuntime& R = *UmHud;
  if (R.Perf < 0) {
    R.Perf = FParse::Param(FCommandLine::Get(), TEXT("S08HudPerf")) ? 1 : 0;
    int32 Block = 90;
    FParse::Value(FCommandLine::Get(), TEXT("S08HudPerfBlock="), Block);
    R.PerfMeter.BlockFrames = FMath::Clamp(Block, 20, 600);
  }
  if (R.Perf != 1) return;
  const bool bAborted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted();
  const bool bLive = Hud.bValid && !Hud.bGameOver && !bAborted && !IsResultScreenShown();
  if (!bLive) {
    if (R.PerfStartAt >= 0.0f && (Hud.bGameOver || bAborted || IsResultScreenShown())) FinishUmHudPerf(TEXT("match-end"));
    return;
  }
  if (R.PerfStartAt < 0.0f) {
    R.PerfStartAt = Elapsed + 8.0f;  // the start hand, the camera and the first snapshots settle
    FS08Trace::Write(FString::Printf(TEXT("HUDPERF start at=%.1f block=%d skip=%d root=umg"), R.PerfStartAt,
                                     R.PerfMeter.BlockFrames, R.PerfMeter.SkipFrames));
    return;
  }
  if (Elapsed < R.PerfStartAt) return;
  const bool bPause = IsEvidenceCaptureBusy() || EvidenceShotQueue.Num() > 0;
  TArray<FString> Lines;
  const bool bShow = R.PerfMeter.Step(static_cast<float>(FPlatformTime::ToMilliseconds(GGameThreadTime)),
                                      static_cast<float>(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles())), bPause,
                                      Lines);
  for (const FString& L : Lines) FS08Trace::Write(L);
  if (bShow != R.bPerfShown) {
    R.bPerfShown = bShow;
    UmHudRoot->SetVisibility(bShow ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  }
}

void AS08FlowGameMode::FinishUmHudPerf(const TCHAR* Why) {
  if (!UmHud.IsValid() || UmHud->Perf != 1) return;
  FUmHudRuntime& R = *UmHud;
  R.Perf = 2;
  if (UmHudRoot && !R.bPerfShown) UmHudRoot->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  R.bPerfShown = true;
  FS08Trace::Write(R.PerfMeter.Summary(Why));
}

void AS08FlowGameMode::TickUmHud() {
  TickUmHudPerf();    // VS-3 HUD budget (-S08HudPerf)
  TickUmExitShots();  // VS-2 / VS-3 exit frames (-S08ExitShots)
  TickUmScreenShots();  // VS-3 SC-01 (-S08ScreenShots)
  // VS-2 HB-12: Hand over an own figure or a lit cell (picked when the pointer moved), the busy loop while in flight
  if (UmHud.IsValid() && UmHudRoot && UmHudRoot->HasCursors()) {
    APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    float MX = -1.0f, MY = -1.0f;
    if (PC && BoardActor && PC->GetMousePosition(MX, MY) && UmHud->BoardCursor.NeedsPick(FVector2D(MX, MY), GFrameCounter)) {
      FIntPoint Cell(-1, -1);
      FString FighterId;
      PickBoardUnderCursor(PC, Cell, FighterId);
      const FS08BoardFighter* F = Fighters.FindByPredicate([&FighterId](const FS08BoardFighter& X) { return X.Id == FighterId; });
      const bool bOwn = F && !F->OwnerId.IsEmpty() && F->OwnerId == ViewerIdNow();
      PC->CurrentMouseCursor =
          UmHud->BoardCursor.Store(FVector2D(MX, MY), GFrameCounter, bOwn, Cell.X >= 0 && BoardActor->IsCellHighlighted(Cell));
    }
    UmHudRoot->TickCursors(HudBusyReason().IsSet() || UmFlowScreensBusy(), FPlatformTime::Seconds());  // VS-7: login
  }
  if (!UmHud.IsValid() || !UmHud->bLayout || !UmHud->Blocks.UmgRoot()) return;
  TickUmInspect();      // VS-4 V4 (H13): INSPECT follows bInspecting / the deck grid
  TickUmCardFlashCue();  // VS-4 CP-21: the done line of the CUE-006 show
  if (UUmHudHand* Hand = UmHud->Hand.Get()) Hand->StepAnimating();  // VS-3 (ВР-VS3-69): the card tweens of the hand
  TickUmTopStrip();  // VS-2 HB-14...HB-16
  TickUmPanels();    // VS-2 HB-18...HB-21
  RefreshUmCombat();  // VS-3 HB-30...HB-33: the staging's clock moves the edges and the centre
  FUmHudRuntime& R = *UmHud;
  // VS-4 HB-35: what changes the choice between snapshots - the staging ends, the slot's hold, a command in flight, the
  // combat centre it sits under
  if (R.Pending.IsValid()) {
    const UUmHudCombatCenter* Centre = R.Combat.GetCenter();
    const FBox2D CentreRect = Centre && UmGameHudSlots::ShownByProperty(Centre) ? Centre->PanelRectSu() : FBox2D(ForceInit);
    const FString Key = FString::Printf(TEXT("%d|%d|%d|%d|%.0f"), CombatStage.IsActive() ? 1 : 0, CardSlot.HoldsEffect() ? 1 : 0,
                                        HudBusyReason().IsSet() ? 1 : 0, static_cast<int32>(CommandUi.Mode),
                                        CentreRect.bIsValid ? CentreRect.Max.Y : -1.0);
    if (Key != R.PendingTickKey) {
      R.PendingTickKey = Key;
      RefreshUmPending();
    }
  }
  // ВР-VS2-73: the Slate command panel (top left until ACTIONS / CENTER, VS-4) starts 8 su under TOP while TOP is shown
  if (const TSharedPtr<SWidget> Cmd = ArtHud.CommandPanel.Pin()) {
    const UUmHudTop* TopW = R.TopStrip.GetTop();
    const float Shift = (TopW && TopW->IsVisible()) ? static_cast<float>(R.Layout.Rect(EUmHudBlock::Top).Max.Y) + 8.0f : 0.0f;
    // VS-4 (ВР-VS4-14): the panel (its remaining buttons) right of a shown UMG source card, never over it - the
    // panel's left is the Slate canvas's 16 su
    const UUmHudSourceSlot* SlotW = R.Slot.Get();
    const FBox2D SlotRect = R.Layout.Rect(EUmHudBlock::SourceSlot);
    const float ShiftX = SlotW && SlotW->GetPhase() != EUmSlotPhase::Hidden && SlotRect.bIsValid
                             ? FMath::Max(0.0f, static_cast<float>(SlotRect.Max.X) + 8.0f - 16.0f)
                             : 0.0f;
    if (!FMath::IsNearlyEqual(Shift, R.CommandShiftSu, 0.5f) || !FMath::IsNearlyEqual(ShiftX, R.CommandShiftXSu, 0.5f)) {
      R.CommandShiftSu = Shift;
      R.CommandShiftXSu = ShiftX;
      Cmd->SetRenderTransform(Shift > 0.0f || ShiftX > 0.0f
                                  ? TOptional<FSlateRenderTransform>(FSlateRenderTransform(FVector2f(ShiftX, Shift)))
                                  : TOptional<FSlateRenderTransform>());
      FS08Trace::Write(FString::Printf(TEXT("HUD-CMD shift=%.0f top=%d shiftX=%.0f slot=%d"), Shift, Shift > 0.0f ? 1 : 0, ShiftX,
                                       ShiftX > 0.0f ? 1 : 0));
    }
    // ВР-VS2-75: an empty command panel (the opponent's turn without a choice) drew a 20 su navy square at the edge
    const float CmdOpacity = (CommandBox.IsValid() && CommandBox->NumSlots() == 0) ? 0.0f : 1.0f;
    if (!FMath::IsNearlyEqual(Cmd->GetRenderOpacity(), CmdOpacity)) Cmd->SetRenderOpacity(CmdOpacity);
  }
  // VS-3 HB-24 (ВР-VS3-22): with the UMG hand the Slate panel holds only lines - transparent while it has none
  {
    const TSharedPtr<SWidget> HandPanel = ArtHud.HandPanel.Pin();
    const bool bEmpty = UmHandOnUmg() && HandPanel.IsValid() && HandBox.IsValid() && HandBox->NumSlots() == 0 &&
                        HandPanel->GetDesiredSize().Y <= 21.0f;
    if (UmHandOnUmg() && HandPanel.IsValid() && !FMath::IsNearlyEqual(HandPanel->GetRenderOpacity(), bEmpty ? 0.0f : 1.0f)) {
      HandPanel->SetRenderOpacity(bEmpty ? 0.0f : 1.0f);
    }
  }
  // VS-4 HB-39...HB-41: the log, the toast stack and the subtitle (the H2 Slate stack of the toast line and the subtitle
  // box is gone: they show only on their rollback -S08SlateHud=toast | sub, 04 §5.1)
  TickUmFeed();
  // VS-4 HB-43: what changes the row between RefreshHud calls - a command in flight ends, the combat window, the result
  TickUmZoneBadges();  // VS-4 FX-38
  if (R.Actions.IsValid()) {
    const FString Key = FString::Printf(TEXT("%d|%d|%d|%d|%d|%d|%d|%d"), Hud.SequenceNumber, Hud.bViewerTurn ? 1 : 0,
                                        Hud.ActionsRemaining, static_cast<int32>(CommandUi.Mode), HudBusyReason().IsSet() ? 1 : 0,
                                        CommandUi.Combat.bPresent ? 1 : 0, CommandUi.bHasPendingChoice ? 1 : 0,
                                        IsResultScreenShown() ? 1 : 0);
    if (Key != R.ActionsTickKey) {
      R.ActionsTickKey = Key;
      RefreshUmActions();
    }
  }
}

void AS08FlowGameMode::WriteUmHudShotLines() {
  if (!UmHud.IsValid()) return;
  if (UmFlowScreensCoverLegacy()) return;  // VS-7 S3: ROOM's countdown / LOADING cover the GAME screen - its blocks are not on screen
  FUmHudRuntime& R = *UmHud;
  FVector2D Viewport(0.0, 0.0);
  if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(Viewport);
  const FIntPoint Window(FMath::RoundToInt(Viewport.X), FMath::RoundToInt(Viewport.Y));
  // once per shot frame (04 §4.5): the class, the canvas, FIELD and the overlap of the persistent blocks
  if (R.bLayout) FS08Trace::Write(R.Layout.TraceLine(Window));
  if (!R.Blocks.UmgRoot()) {
    FS08Trace::Write(FString::Printf(TEXT("SHOT widget id=UI-SCR-GAME impl=slate state=%s fighter=none bbox=0,0,%d,%d "
                                          "geom=painted visible=1 twin=0 source=slate"),
                                     Hud.bGameOver ? TEXT("over") : Hud.bViewerTurn ? TEXT("own") : TEXT("opp"), Window.X,
                                     Window.Y));
    return;
  }
  if (UmHudRoot) {
    if (UUmGameHud* Game = UmHudRoot->GetGameHud()) {
      const bool bCombat = CommandUi.Combat.bPresent || CombatStage.IsActive();
      const bool bPending = CommandUi.Mode == ES09CommandMode::PendingChoice;
      Game->SetScreenState(Hud.bGameOver ? TEXT("over")
                           : bCombat     ? TEXT("combat")
                           : bPending    ? TEXT("pending")
                           : Hud.bViewerTurn ? TEXT("own")
                                             : TEXT("opp"));
      TArray<FString> Lines;
      Game->CollectShotLines(Lines, Window);
      for (const FString& L : Lines) FS08Trace::Write(L);
    }
  }
  // VS-2 HB-14...HB-16: UI-HUD-TOP, UI-HUD-CONN, UI-HUD-STATUS, UI-HUD-BANNER (the drawn plate / chip / capsule)
  TArray<FString> StripLines;
  R.TopStrip.CollectShotLines(StripLines, [this](UWidget* W) {
    FS08ScreenRect Rect;
    if (W) WidgetViewportRect(W->GetCachedWidget(), Rect);
    return Rect;
  });
  // VS-3 HB-24 / HB-25: UI-HUD-HAND and one HUD-HAND line per card (no key, no name)
  if (const UUmHudHand* Hand = R.Hand.Get()) {
    TArray<FString> HandLines;
    Hand->CollectShotLines(HandLines);
    for (const FString& L : HandLines) FS08Trace::Write(L);
  }
  // VS-3 HB-27 / HB-28: UI-HUD-DECKS and UI-HUD-DECKPANEL (counts only)
  {
    TArray<FString> DeckLines;
    R.DeckBlocks.CollectShotLines(DeckLines);
    for (const FString& L : DeckLines) FS08Trace::Write(L);
  }
  // VS-3 HB-30...HB-33: UI-HUD-COMBAT-EDGE (own, opp) and UI-HUD-COMBAT (no card name, no text)
  {
    TArray<FString> CombatLines;
    R.Combat.CollectShotLines(CombatLines);
    for (const FString& L : CombatLines) FS08Trace::Write(L);
  }
  // VS-4 HB-35 / HB-37: UI-HUD-PENDING and UI-HUD-SLOT (no card name, no text, no card id)
  {
    TArray<FString> PendingLines;
    if (const UUmHudPending* P = R.Pending.Get()) P->CollectShotLines(PendingLines);
    if (const UUmHudSourceSlot* W = R.Slot.Get()) W->CollectShotLines(PendingLines);
    for (const FString& L : PendingLines) FS08Trace::Write(L);
  }
  // VS-4 FX-38: the zone icons of the hovered space (one 'SHOT widget id=zone' line, keys only)
  if (const UUmZoneBadges* Z = R.Zones.Get()) {
    TArray<FString> ZoneLines;
    Z->CollectShotLines(ZoneLines);
    for (const FString& L : ZoneLines) FS08Trace::Write(L);
  }
  // VS-4 V4 (H13): UI-SCR-INSPECT + the CARD-ART lines of its cards (no name, no value, no text)
  if (const UUmScreenInspect* S = R.Inspect.Get()) {
    TArray<FString> InspectLines;
    S->CollectShotLines(InspectLines);
    for (const FString& L : InspectLines) FS08Trace::Write(L);
  }
  // VS-4 HB-43: UI-HUD-ACTIONS (the cell states and reasons, no text)
  if (const UUmHudActions* A = R.Actions.Get()) {
    TArray<FString> ActionLines;
    A->CollectShotLines(ActionLines);
    for (const FString& L : ActionLines) FS08Trace::Write(L);
  }
  // VS-4 HB-39...HB-41: UI-HUD-LOG, UI-HUD-TOAST, UI-HUD-SUB (counts and places only, no text)
  {
    TArray<FString> FeedLines;
    R.Feed.CollectShotLines(FeedLines, R.Layout.PxPerSu);
    for (const FString& L : FeedLines) FS08Trace::Write(L);
  }
  TArray<FString> PanelLines;  // VS-2 HB-18...HB-21: UI-HUD-PANEL-LOC, UI-HUD-PANEL-OPP, UI-HUD-OPP-HAND
  R.Panels.CollectShotLines(PanelLines, [this](UWidget* W) {
    FS08ScreenRect Rect;
    if (W) WidgetViewportRect(W->GetCachedWidget(), Rect);
    return Rect;
  });
  // ВР-VS2-77: a block first shown in this frame has no geometry yet - its line waits for the late block
  R.LateIds.Reset();
  for (const TArray<FString>* Group : {&StripLines, &PanelLines}) {
    for (const FString& L : *Group) {
      FString Id;
      if (L.Contains(TEXT(" geom=unpainted visible=1 ")) && FParse::Value(*L, TEXT("id="), Id) && Id.StartsWith(TEXT("UI-HUD-"))) {
        R.LateIds.Add(Id);
        FS08Trace::Write(FString::Printf(TEXT("SHOT widget-late id=%s reason=first-frame"), *Id));
      } else {
        FS08Trace::Write(L);
      }
    }
  }
  // VS-2 HB-12: the cursor Slate drew for this frame (or the system cursor of the rollback)
  const APlayerController* CursorPC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  FS08Trace::Write(UmHudRoot && UmHudRoot->HasCursors()
                       ? UmHudRoot->CursorShotLine(CursorPC ? CursorPC->CurrentMouseCursor.GetValue() : EMouseCursor::Default)
                       : UmCursor::SystemShotLine(TEXT("-S08SlateHud=cursor")));
  // VS-2 CP-08: the portrait circles of PANEL-LOC / PANEL-OPP (ВР-CP10; check-trace: scale <= 1.6, no monogram)
  for (const US08TurnPortraitWidget* Portrait : {OwnPortrait.Get(), OpponentPortrait.Get()}) {
    if (Portrait && Portrait->IsVisible()) FS08Trace::Write(Portrait->PortraitShotLine(TEXT("panel")));
  }
}

void AS08FlowGameMode::BuildUmTopStrip() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  const TArray<FString> Lines = UmHud->TopStrip.Build(
      *Game, UmHud->Blocks, HudPress, [WeakThis](const FS09HudPressOutcome& Outcome, const TCHAR* What) {
        AS08FlowGameMode* Self = WeakThis.Get();
        const FString Which(What);
        if (Self) Self->HandleHudPressOutcome(Outcome, TFunction<FS09Reason()>(), [WeakThis, Which]() {
          if (AS08FlowGameMode* S = WeakThis.Get()) S->HandleUmTopPress(*Which);
        });
      });
  ArtHud.PendingTrace.Append(Lines);
}

void AS08FlowGameMode::BuildUmPanels() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game || !S08ArtLook::Enabled()) return;
  const FS08ArtHudPlateStyle Chips;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  ArtHud.PendingTrace.Append(UmHud->Panels.Build(
      *Game, UmHud->Blocks, TurnHudLook, Chips.TeamChipColor(0), Chips.TeamChipColor(1), HudPress,
      [WeakThis](const FS09HudPressOutcome& Outcome, const TCHAR* Which) {
        const bool bOpp = FCString::Strcmp(Which, TEXT("opp")) == 0;
        if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleHudPressOutcome(Outcome, TFunction<FS09Reason()>(), [WeakThis, bOpp]() {
          // 04 §2.2 / §2.3: a click on a panel (or the opponent's backs) opens the deck panel of its side (HB-28 later)
          if (AS08FlowGameMode* S = WeakThis.Get()) S->ToggleDeckPanel(bOpp ? ES09DeckSide::Opponent : ES09DeckSide::Own, TEXT("panel"));
        });
      },
      [WeakThis]() {
        FS09CardView Hidden;  // 04 §2.3: the backs never open a face - the inspector says "Скрытая информация"
        Hidden.bHidden = true;
        Hidden.CardId = TEXT("hidden");
        if (AS08FlowGameMode* Self = WeakThis.Get()) {
          Self->NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::OppHand));
          Self->InspectCard(Hidden);
          Self->RefreshHud();
        }
      }));
  if (!UmHud->Panels.PanelsOnUmg()) return;
  OwnPortrait = UmHud->Panels.GetLoc()->Portrait;
  OpponentPortrait = UmHud->Panels.GetOpp()->Portrait;
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-TURN config portraits=1 %s ringIcon=%d banner=%d panels=umg"),
                                          *TurnHudLook.Describe(), OwnPortrait->HasRingIcon() ? 1 : 0,
                                          FMath::RoundToInt(FS09TurnCue::BannerMs)));
}

void AS08FlowGameMode::TickUmPanels() {
  FUmPanelsTick T;
  // with the live match HUD; the result screen keeps them only in its board view (TickTurnHud's rule)
  const int64 Now = static_cast<int64>(NowMs());
  T.bShow = Hud.bValid && (!IsResultScreenShown() || ResultView.BoardBarAlpha(Now) > 0.0f);
  T.Own = Hud.ViewerPanel();
  T.Opp = Hud.OpponentPanel();
  T.Fighters = &HudFighters();
  T.OwnHeroName = T.Own ? PlayerHeroName(T.Own->PlayerId) : FString();
  T.OppHeroName = T.Opp ? PlayerHeroName(T.Opp->PlayerId) : FString();
  T.bViewerTurn = Hud.bViewerTurn;
  T.bGameOver = Hud.bGameOver;
  T.bBotActing = Flow.IsValid() && Flow->IsBotActing();
  // the mark of the death stage (contact + 1100), or a fighter shown dead that no stage holds (a join mid-game)
  T.IsCrossed = [this, Now](const FString& Id) {
    if (DeathStage.HeartState(Id, Now) != ES09HeartState::Alive) return true;
    const FS08BoardFighter* F = HudFighters().FindByPredicate([&Id](const FS08BoardFighter& X) { return X.Id == Id; });
    return F && F->Health <= 0 && !DeathStage.IsStaged(Id);
  };
  UmHud->Panels.Tick(T);
}

float AS08FlowGameMode::UmHudPanelLocRightSu() const {
  // -1: the panels are not UMG (the Slate column rule); 0: PANEL-LOC is hidden; else its right edge (su)
  if (!UmHud.IsValid() || !UmHud->Panels.PanelsOnUmg()) return -1.0f;
  const UUmHudPlayerPanel* Loc = UmHud->Panels.GetLoc();
  const FBox2D Rect = UmHud->Layout.Rect(EUmHudBlock::PanelLoc);
  return Loc && UmGameHudSlots::ShownByProperty(Loc) && Rect.bIsValid ? static_cast<float>(Rect.Max.X) : 0.0f;
}

void AS08FlowGameMode::TickUmTopStrip() {
  FUmTopStripTick T;
  // with the live match HUD, like the portraits; the result screen takes the whole picture
  T.bShow = Hud.bValid && !IsResultScreenShown();
  T.TurnCount = Hud.TurnCount;
  const bool bStarted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started;
  T.bStreamReady = !bStarted || Flow->IsStreamReady();
  T.bStarted = bStarted;  // VS-5 E4: wasReady latches in the match only (the start is syncing, not lost)
  T.bManeuverSlow = bStarted && Flow->IsCommandSlow();
  T.bInFlight = HudBusyReason().IsSet();
  T.bRecovering = bStarted && Flow->IsAwaitingStateRecovery();
  T.NowSeconds = FPlatformTime::Seconds();
  T.Cue = &TurnCue;
  T.CueNowMs = static_cast<double>(NowMs());
  const FString ConnLine = UmHud->TopStrip.Tick(T);
  if (!ConnLine.IsEmpty() && bStarted) FS08Trace::Write(FString::Printf(TEXT("%s seq=%d"), *ConnLine, Hud.SequenceNumber));
}

bool AS08FlowGameMode::ApplyUmHudStatus(const FS09TurnStatusInput& In) {
  return UmHud.IsValid() && !UmHudBlockOnSlate(TEXT("status")) && UmHud->TopStrip.ApplyStatus(In);
}

void AS08FlowGameMode::HandleUmTopPress(const TCHAR* What) {
  // ВР-VS2-44: «≡» is Esc without a selection -> PAUSE (SC-24, step H16; until that screen exists the press is answered,
  // CUE-003 in HandleHudPressOutcome, and traced); «Журнал» toggles the LOG list of class S (VS-4 HB-39)
  const bool bLog = FCString::Strcmp(What, TEXT("log")) == 0;
  if (bLog && UmHud.IsValid() && UmHud->Feed.LogOnUmg()) {
    UmHud->Feed.SetLogOpen(!UmHud->Feed.IsLogOpen());
    FS08Trace::Write(FString::Printf(TEXT("HUD-TOP press=log target=UI-HUD-LOG open=%d"), UmHud->Feed.IsLogOpen() ? 1 : 0));
    return;
  }
  if (!bLog && OpenUmPause(TEXT("top"))) {  // VS-7 S4 SC-24
    FS08Trace::Write(TEXT("HUD-TOP press=menu target=UI-SCR-PAUSE"));
    return;
  }
  FS08Trace::Write(FString::Printf(TEXT("HUD-TOP press=%s target=%s pending=1"), What, bLog ? TEXT("UI-HUD-LOG") : TEXT("UI-SCR-PAUSE")));
}

void AS08FlowGameMode::UmGalleryBegin(int32 SizePx) {
  const TCHAR* Cmd = FCommandLine::Get();
  int32 Page = 0;
  const bool bSkins = FParse::Param(Cmd, TEXT("S08IconGallerySkins")) || FParse::Value(Cmd, TEXT("S08IconGallerySkins="), Page);
  int32 Variant = 0;
  const bool bButtons = FParse::Param(Cmd, TEXT("S08IconGalleryButtons")) || FParse::Value(Cmd, TEXT("S08IconGalleryButtons="), Variant);
  const bool bTopStrip = FParse::Param(Cmd, TEXT("S08IconGalleryTopStrip"));  // VS-2 HB-14...HB-16
  int32 PanelsPage = 1;  // VS-2 HB-18...HB-21
  const bool bPanels = FParse::Param(Cmd, TEXT("S08IconGalleryPanels")) || FParse::Value(Cmd, TEXT("S08IconGalleryPanels="), PanelsPage);
  int32 CardsPage = 1;  // VS-3 CP-03...CP-20 (UI/UmCardGallery.h)
  const bool bCards = FParse::Param(Cmd, TEXT("S08IconGalleryCards")) || FParse::Value(Cmd, TEXT("S08IconGalleryCards="), CardsPage);
  FString HandBoard;  // VS-3 HB-24 / HB-25 (UI/UmHandGallery.h): -S08IconGalleryHand=marmoreal|sarpedon
  const bool bHand = FParse::Value(Cmd, TEXT("S08IconGalleryHand="), HandBoard);
  FString DecksBoard;  // VS-3 HB-27 / HB-28 / HB-47 (UI/UmDecksGallery.h): -S08IconGalleryDecks=marmoreal|sarpedon
  const bool bDecks = FParse::Value(Cmd, TEXT("S08IconGalleryDecks="), DecksBoard);
  // VS-3 HB-30...HB-33 / SC-01 (UI/UmCombatGallery.h): -S08IconGalleryCombat=<board>, -S08IconGalleryConfirm=<board>
  FString CombatBoard;
  const bool bConfirm = FParse::Value(Cmd, TEXT("S08IconGalleryConfirm="), CombatBoard);
  const bool bCombat = bConfirm || FParse::Value(Cmd, TEXT("S08IconGalleryCombat="), CombatBoard);
  FString PendingBoard;  // VS-4 HB-35 / HB-37 (UI/UmPendingGallery.h): -S08IconGalleryPending=marmoreal|sarpedon
  const bool bPending = FParse::Value(Cmd, TEXT("S08IconGalleryPending="), PendingBoard);
  FString FeedBoard;  // VS-4 HB-39...HB-41 (UI/UmFeedGallery.h): -S08IconGalleryFeed=marmoreal|sarpedon
  const bool bFeed = FParse::Value(Cmd, TEXT("S08IconGalleryFeed="), FeedBoard);
  FString ActionsBoard;  // VS-4 HB-43 (UI/UmActionsGallery.h): -S08IconGalleryActions=marmoreal|sarpedon
  const bool bActions = FParse::Value(Cmd, TEXT("S08IconGalleryActions="), ActionsBoard);
  FString WorldBoard;  // VS-4 HB-45 / HB-46 / FX-38 (UI/UmWorldGallery.h): -S08IconGalleryWorld=marmoreal|sarpedon
  const bool bWorld = FParse::Value(Cmd, TEXT("S08IconGalleryWorld="), WorldBoard);
  FString InspectBoard;  // VS-4 V4 SC-21...SC-23 / CP-22 (UI/UmInspectGallery.h): -S08IconGalleryInspect=marmoreal|sarpedon
  const bool bInspect = FParse::Value(Cmd, TEXT("S08IconGalleryInspect="), InspectBoard);
  if (!bSkins && !bButtons && !bTopStrip && !bPanels && !bCards && !bHand && !bDecks && !bCombat && !bPending && !bFeed && !bActions &&
      !bWorld && !bInspect) {
    return;
  }
  if (IconGallery) IconGallery->SetVisibility(ESlateVisibility::Collapsed);  // the sheet takes the screen
  // the canvas of the sheet: the applied HUD scale (BeginPlay may run before the first window apply - the sheet is
  // built again on every OnUiScaleChanged, which also covers a window or UI-scale change)
  const int32 PageIndex = FMath::Max(0, Page - 1);
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  auto Build = [WeakThis, bSkins, bTopStrip, bPanels, PanelsPage, PageIndex, Variant, SizePx, bCards, CardsPage, bHand,
                HandBoard, bDecks, DecksBoard, bCombat, bConfirm, CombatBoard, bPending, PendingBoard, bFeed, FeedBoard, bActions,
                ActionsBoard, bWorld, WorldBoard, bInspect, InspectBoard]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->GetWorld()) return;
    FVector2D Viewport(1920.0, 1080.0);
    if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(Viewport);
    const FUmHudScaleState& Scale = UmHudScale::Current();
    const float PxPerSu = Scale.Window.X > 0 ? Scale.PxPerSu() : 1.0f;
    if (Self->UmGallery) Self->UmGallery->RemoveFromParent();
    if (bInspect) {
      UUmInspectGalleryWidget* Sheet = CreateWidget<UUmInspectGalleryWidget>(Self->GetWorld(), UUmInspectGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(InspectBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bWorld) {
      UUmWorldGalleryWidget* Sheet = CreateWidget<UUmWorldGalleryWidget>(Self->GetWorld(), UUmWorldGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(WorldBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bActions) {
      UUmActionsGalleryWidget* Sheet = CreateWidget<UUmActionsGalleryWidget>(Self->GetWorld(), UUmActionsGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(ActionsBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bFeed) {
      UUmFeedGalleryWidget* Sheet = CreateWidget<UUmFeedGalleryWidget>(Self->GetWorld(), UUmFeedGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(FeedBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bPending) {
      UUmPendingGalleryWidget* Sheet = CreateWidget<UUmPendingGalleryWidget>(Self->GetWorld(), UUmPendingGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(PendingBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bCombat) {
      UUmCombatGalleryWidget* Sheet = CreateWidget<UUmCombatGalleryWidget>(Self->GetWorld(), UUmCombatGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(CombatBoard, Viewport / PxPerSu, PxPerSu, bConfirm)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bDecks) {
      UUmDecksGalleryWidget* Sheet = CreateWidget<UUmDecksGalleryWidget>(Self->GetWorld(), UUmDecksGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(DecksBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bHand) {
      UUmHandGalleryWidget* Sheet = CreateWidget<UUmHandGalleryWidget>(Self->GetWorld(), UUmHandGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(HandBoard, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bCards) {
      UUmCardsGalleryWidget* Sheet = CreateWidget<UUmCardsGalleryWidget>(Self->GetWorld(), UUmCardsGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(CardsPage, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bPanels) {
      UUmPanelsGalleryWidget* Sheet = CreateWidget<UUmPanelsGalleryWidget>(Self->GetWorld(), UUmPanelsGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(FMath::Clamp(PanelsPage, 1, 3) - 1, Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);  // 3: CP-09...12
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bTopStrip) {
      UUmTopStripGalleryWidget* Sheet = CreateWidget<UUmTopStripGalleryWidget>(Self->GetWorld(), UUmTopStripGalleryWidget::StaticClass());
      if (!Sheet) return;
      for (const FString& Line : Sheet->Build(Viewport / PxPerSu, PxPerSu)) FS08Trace::Write(Line);
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    if (bSkins) {
      UUmSkinGalleryWidget* Sheet = CreateWidget<UUmSkinGalleryWidget>(Self->GetWorld(), UUmSkinGalleryWidget::StaticClass());
      if (!Sheet) return;
      FS08Trace::Write(Sheet->Build(PageIndex, Viewport / PxPerSu, PxPerSu));
      Sheet->AddToViewport(1001);
      Self->UmGallery = Sheet;
      return;
    }
    UUmButtonGalleryWidget* Sheet = CreateWidget<UUmButtonGalleryWidget>(Self->GetWorld(), UUmButtonGalleryWidget::StaticClass());
    if (!Sheet) return;
    for (const FString& Line : Sheet->Build(Viewport / PxPerSu, Variant)) FS08Trace::Write(Line);
    FS08Trace::Write(FString::Printf(TEXT("UMGALLERY buttons pxPerSu=%.3f size=%d"), PxPerSu, SizePx));
    Sheet->AddToViewport(1001);
    Self->UmGallery = Sheet;
  };
  Build();
  UmHudScale::OnUiScaleChanged().AddWeakLambda(this, [Build](const FUmHudScaleState&) { Build(); });
}

void AS08FlowGameMode::UmGalleryAt(float TMs) {
  // VS-3: the card sheets freeze every card at the gallery time (motion sheets of CP-16...CP-20)
  if (UUmCardsGalleryWidget* Cards = Cast<UUmCardsGalleryWidget>(UmGallery)) {
    for (const FString& Line : Cards->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-3 HB-24 / HB-25: the hand sheet - one state per second of the gallery clock
  if (UUmHandGalleryWidget* HandSheet = Cast<UUmHandGalleryWidget>(UmGallery)) {
    for (const FString& Line : HandSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-3 HB-27 / HB-28 / HB-47: the deck sheet - one state per second of the gallery clock
  if (UUmDecksGalleryWidget* DecksSheet = Cast<UUmDecksGalleryWidget>(UmGallery)) {
    for (const FString& Line : DecksSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-3 HB-30...HB-33 / SC-01: the combat states (one per second) or the confirm modal
  if (UUmCombatGalleryWidget* CombatSheet = Cast<UUmCombatGalleryWidget>(UmGallery)) {
    for (const FString& Line : CombatSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-4 HB-35 / HB-37: the choice and source-card states (one per second)
  if (UUmFeedGalleryWidget* FeedSheet = Cast<UUmFeedGalleryWidget>(UmGallery)) {
    for (const FString& Line : FeedSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  if (UUmPendingGalleryWidget* PendingSheet = Cast<UUmPendingGalleryWidget>(UmGallery)) {
    for (const FString& Line : PendingSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-4 HB-43: the ACTIONS states (one per second)
  if (UUmActionsGalleryWidget* ActionsSheet = Cast<UUmActionsGalleryWidget>(UmGallery)) {
    for (const FString& Line : ActionsSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-4 V4: the INSPECT states (one per second)
  if (UUmInspectGalleryWidget* InspectSheet = Cast<UUmInspectGalleryWidget>(UmGallery)) {
    for (const FString& Line : InspectSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
  // VS-4 HB-45 / HB-46 / FX-38: the world layer states (one per second)
  if (UUmWorldGalleryWidget* WorldSheet = Cast<UUmWorldGalleryWidget>(UmGallery)) {
    for (const FString& Line : WorldSheet->SetClockMs(TMs)) FS08Trace::Write(Line);
  }
}

// ------------------------------------------------------------------------------------------------ VS-3 HB-24 / HB-25

void AS08FlowGameMode::BuildUmHand() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  if (UmHud->Blocks.IsSlate(FName(TEXT("hand")))) {
    ArtHud.PendingTrace.Add(TEXT("HUD-HAND-UMG impl=slate reason=-S08SlateHud=hand"));
    return;
  }
  UUmHudHand* Hand = CreateWidget<UUmHudHand>(Game, UUmHudHand::WidgetClass());
  if (!Hand || !Game->SetBlock(EUmGameSlot::Hand, Hand)) {
    ArtHud.PendingTrace.Add(TEXT("HUD-HAND-UMG impl=umg created=0 reason=create-failed"));
    return;
  }
  UmHud->Hand = Hand;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  Hand->SetInput(
      HudPress,
      [WeakThis](const FS09HudPressOutcome& Outcome, const FString& Id) {
        if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmHandPress(Outcome, Id);
      },
      [WeakThis](const FString& Id) {
        if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmHandInspect(Id);
      },
      [WeakThis](const FString& Id) {
        if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmHandPlay(Id);
      });
  Hand->SetVisibility(ESlateVisibility::Collapsed);  // RefreshUmHand shows it with the live match HUD
  FString Missing;
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-HAND-UMG impl=umg created=1 source=%s parts=%d missing=%s"),
                                          *Hand->SourceName(), Hand->HasAllParts(&Missing) ? 1 : 0,
                                          Missing.IsEmpty() ? TEXT("-") : *Missing));
}

bool AS08FlowGameMode::UmHandOnUmg() const { return UmHud.IsValid() && UmHud->Hand.IsValid(); }

bool AS08FlowGameMode::RefreshUmHand() {
  if (!UmHandOnUmg()) return false;
  FUmHudRuntime& R = *UmHud;
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  // the own hero slug: the scan keys heroSlug:cardSlug and the back (kept when the hero leaves the projection)
  if (Own) {
    for (const FS08BoardFighter& F : Fighters) {
      if (F.OwnerId != Own->PlayerId || F.HeroSlug.IsEmpty()) continue;
      R.HandHeroSlug = F.HeroSlug;
      if (F.bIsHero) break;
    }
  }
  UmHudHand::FGatherIn In;
  In.Own = Own;
  In.Ui = &CommandUi;
  In.Fighters = &Fighters;
  In.ViewerId = ViewerIdNow();
  In.InspectedIndex = bInspecting && InspectedSource == 0 ? InspectedHandIndex : -1;
  In.bLowered = HandLower.IsLowered();
  In.bStartHand = Hud.TurnCount <= 1;
  In.HeroSlug = R.HandHeroSlug;
  FUmHandModel Model = UmHudHand::Gather(In);
  // the live match HUD only (the result screen, an aborted room and the lobby have no hand)
  const bool bAborted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted();
  Model.bShow = Model.bShow && Hud.bValid && !Hud.bGameOver && !bAborted && Own != nullptr;
  R.Hand->ApplyModel(Model);
  UmNoteCardFlashes(R.Hand->TakePlayedFlashes(), Hud.SequenceNumber);  // VS-4 CP-21: CUE-006 (G-CUE)
  return true;
}

void AS08FlowGameMode::HandleUmHandPress(const FS09HudPressOutcome& Outcome, const FString& InstanceId) {
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  // DE-014 / UI-INP-011: the old hand.<instance> action - the card by its CURRENT position (a snapshot may have moved it)
  HandleHudPressOutcome(Outcome, TFunction<FS09Reason()>(), [WeakThis, InstanceId]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    const FS09PlayerPanel* Own = Self ? Self->Hud.ViewerPanel() : nullptr;
    if (!Own) return;
    const int32 Index = Own->Cards.IndexOfByPredicate([&InstanceId](const FS09CardView& C) { return C.InstanceId == InstanceId; });
    if (Index == INDEX_NONE) {
      Self->ShowReason(FS09Reason::Make(TEXT("why.state.changed")), 3.0f);
      return;
    }
    Self->HandleHandCardClick(Index, ES09InputSource::Click);
  });
}

void AS08FlowGameMode::HandleUmHandPlay(const FString& InstanceId) {
  // UI-INP-003: the double click plays - its first click already selected the card; the scheme and the defense card
  // then go as with Enter (an attack goes on its own once complete, DE-020)
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  if (!Own) return;
  const int32 Index = Own->Cards.IndexOfByPredicate([&InstanceId](const FS09CardView& C) { return C.InstanceId == InstanceId; });
  if (Index == INDEX_NONE) return;
  const bool bScheme = CommandUi.Mode == ES09CommandMode::SchemeChoice;
  const bool bDefense = CommandUi.Mode == ES09CommandMode::CombatDefense;
  if (!bScheme && !bDefense) return;
  const FString& Selected = bScheme ? CommandUi.SchemeCardId : CommandUi.DefenseCardId;
  if (Selected != InstanceId) HandleHandCardClick(Index, ES09InputSource::Click);
  FS08Trace::Write(FString::Printf(TEXT("HUD-HAND play=%s index=%d"), bScheme ? TEXT("scheme") : TEXT("defense"), Index));
  if ((bScheme ? CommandUi.SchemeCardId : CommandUi.DefenseCardId) == InstanceId) ConfirmCombat();
}

void AS08FlowGameMode::HandleUmHandInspect(const FString& InstanceId) {
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  if (!Own) return;
  const int32 Index = Own->Cards.IndexOfByPredicate([&InstanceId](const FS09CardView& C) { return C.InstanceId == InstanceId; });
  if (Index == INDEX_NONE) return;
  // 04 §2.6: the right button opens the inspector on the card (VS-4 H13: the UMG INSPECT)
  NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Hand));
  InspectCard(Own->Cards[Index]);
  InspectedHandIndex = Index;
  DiscardBrowserIndex = -1;
  InspectedSource = 0;
  RefreshHud();
}

bool AS08FlowGameMode::UmHudCursorOverHand(float X, float Y) const {
  if (!UmHandOnUmg() || !UmHud->bLayout) return false;
  const UUmHudHand* Hand = UmHud->Hand.Get();
  if (!UmGameHudSlots::ShownByProperty(Hand) || Hand->GetRow().CardPos.Num() == 0) return false;
  // the resting row (the raise of a selected card included), not the lowered one: no flicker at its top edge
  const UmHudHand::FRow& Row = Hand->GetRow();
  const float Px = UmHud->Layout.PxPerSu > 0.0f ? UmHud->Layout.PxPerSu : 1.0f;
  const float Top = (Row.CardTopSu - UmHudHand::CaptionSu) * Px;
  return X >= Row.LeftSu * Px && X <= Row.RightSu * Px && Y >= Top;
}

// ------------------------------------------------------------------------------------------------ VS-3 HB-27 / HB-28

namespace {
/** The hero slug of a player's hero fighter (the back of his deck, the scan key of his cards); '' when unknown. */
FString UmDeckHeroSlug(const TArray<FS08BoardFighter>& InFighters, const FString& PlayerId) {
  FString Slug;
  for (const FS08BoardFighter& F : InFighters) {
    if (F.OwnerId != PlayerId || F.HeroSlug.IsEmpty()) continue;
    Slug = F.HeroSlug;
    if (F.bIsHero) break;
  }
  return Slug;
}
}  // namespace

void AS08FlowGameMode::BuildUmDecks() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  // every press answers in the frame of its release (UI-INP-011), then the game mode acts
  auto Answer = [WeakThis](const FS09HudPressOutcome& Outcome, TFunction<void(AS08FlowGameMode&)> Act) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) {
      Self->HandleHudPressOutcome(Outcome, TFunction<FS09Reason()>(), [WeakThis, Act]() {
        if (AS08FlowGameMode* S = WeakThis.Get()) Act(*S);
      });
    }
  };
  FUmDeckBlocks::FCallbacks C;
  // HB-27 p. 3: the deck chip - the panel on «Ваша»; the discard chip - the same with «Только сброс»
  C.OnChip = [Answer](const FS09HudPressOutcome& O, bool bDiscard) {
    Answer(O, [bDiscard](AS08FlowGameMode& S) {
      if (bDiscard) {
        S.OpenUmDeckDiscard(TEXT("chip"));
      } else {
        S.ToggleDeckPanel(ES09DeckSide::Own, TEXT("chip"));
      }
    });
  };
  // a tab switches the side; the selected tab stays (ToggleDeckPanel would close it)
  C.Panel.OnTab = [Answer](const FS09HudPressOutcome& O, ES09DeckSide Side) {
    Answer(O, [Side](AS08FlowGameMode& S) {
      if (!S.DeckPanel.IsOpen() || S.DeckPanel.Side() != Side) S.ToggleDeckPanel(Side, TEXT("tab"));
    });
  };
  C.Panel.OnClose = [Answer](const FS09HudPressOutcome& O) { Answer(O, [](AS08FlowGameMode& S) { S.CloseDeckPanel(TEXT("button")); }); };
  C.Panel.OnFilter = [Answer](const FS09HudPressOutcome& O) {
    Answer(O, [](AS08FlowGameMode& S) {
      S.UmHud->DeckBlocks.SetFilter(!S.UmHud->DeckBlocks.GetFilter());
      FS08Trace::Write(FString::Printf(TEXT("DECK panel filter discard=%d why=button"), S.UmHud->DeckBlocks.GetFilter() ? 1 : 0));
      S.RefreshUmDecks();
    });
  };
  C.Panel.OnRow = [Answer](const FS09HudPressOutcome& O, const FString& CardId) {
    Answer(O, [CardId](AS08FlowGameMode& S) { S.HandleUmDeckRowInspect(CardId); });
  };
  C.Panel.OnAll = [Answer](const FS09HudPressOutcome& O, ES09DeckSide Side) {
    Answer(O, [Side](AS08FlowGameMode& S) { S.OpenUmInspectDeck(Side == ES09DeckSide::Own); });  // VS-4 SC-23
  };
  C.Panel.OnRetry = [Answer](const FS09HudPressOutcome& O) {
    Answer(O, [](AS08FlowGameMode& S) {
      if (S.Flow.IsValid()) S.Flow->EnsureDeckLists(/*bRetryFailed=*/true);
      S.RefreshHud();
    });
  };
  ArtHud.PendingTrace.Append(UmHud->DeckBlocks.Build(*Game, UmHud->Blocks, HudPress, MoveTemp(C)));
}

bool AS08FlowGameMode::UmDeckPanelOnUmg() const { return UmHud.IsValid() && UmHud->DeckBlocks.PanelOnUmg(); }

void AS08FlowGameMode::RefreshUmDecks() {
  if (!UmHud.IsValid() || !UmHud->bLayout) return;
  FUmHudRuntime& R = *UmHud;
  FUmDeckBlocksInput In;
  In.Layout = &R.Layout;
  const bool bAborted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted();
  In.bLive = Hud.bValid && !Hud.bGameOver && !bAborted && !IsResultScreenShown();
  In.bRu = UmCardMedia::PreferredLang() != TEXT("en");
  In.Own = Hud.ViewerPanel();
  In.Opp = Hud.OpponentPanel();
  if (In.Own) {
    In.OwnHero = PlayerHeroName(In.Own->PlayerId);
    In.OwnSlug = UmDeckHeroSlug(Fighters, In.Own->PlayerId);
  }
  if (In.Opp) {
    In.OppHero = PlayerHeroName(In.Opp->PlayerId);
    In.OppSlug = UmDeckHeroSlug(Fighters, In.Opp->PlayerId);
  }
  In.Lists = &DeckLists;
  const FS08FlowController::EDeckListsState State =
      Flow.IsValid() ? Flow->GetDeckListsState() : FS08FlowController::EDeckListsState::None;
  In.ListState = bBenchDeckPanel || State == FS08FlowController::EDeckListsState::Loaded ? EUmDeckListState::Loaded
                 : State == FS08FlowController::EDeckListsState::Failed                ? EUmDeckListState::Failed
                                                                                       : EUmDeckListState::Loading;
  In.bPanelOpen = DeckPanel.IsOpen();
  In.bPanelVisible = DeckPanel.IsVisible(NowMs());
  In.Side = DeckPanel.Side();
  In.Hand = R.Hand.Get();
  const FString ModelLine = R.DeckBlocks.Refresh(In);
  if (!ModelLine.IsEmpty() && ModelLine != DeckModelTraced) {
    FS08Trace::Write(ModelLine);
    DeckModelTraced = ModelLine;
  }
}

bool AS08FlowGameMode::TickUmDeckPanel(float Alpha) {
  if (!UmDeckPanelOnUmg()) return false;
  // the Slate panel stays collapsed: the UMG panel draws
  if (DeckPanelBorder.IsValid() && DeckPanelBorder->GetVisibility() != EVisibility::Collapsed) {
    DeckPanelBorder->SetVisibility(EVisibility::Collapsed);
  }
  const FString Loader = UmHud->DeckBlocks.TickPanel(Alpha, DeckPanel.IsOpen(), static_cast<double>(NowMs()),
                                                     S08IconMotion::IsReducedMotion(), [this]() { RefreshUmDecks(); });
  if (!Loader.IsEmpty()) FS08Trace::Write(Loader);
  return true;
}

void AS08FlowGameMode::OpenUmDeckDiscard(const TCHAR* Why) {
  if (!UmDeckPanelOnUmg()) return;
  FUmDeckBlocks& B = UmHud->DeckBlocks;
  // D / the discard chip: «Ваша» with «Только сброс»; again on that view - closed
  if (DeckPanel.IsOpen() && DeckPanel.Side() == ES09DeckSide::Own && B.GetFilter()) {
    CloseDeckPanel(Why);
    return;
  }
  if (DeckPanel.IsOpen()) {
    if (DeckPanel.Side() != ES09DeckSide::Own) ToggleDeckPanel(ES09DeckSide::Own, Why);
    B.SetFilter(true);
  } else {
    B.RequestFilterOnOpen();
    ToggleDeckPanel(ES09DeckSide::Own, Why);
  }
  FS08Trace::Write(FString::Printf(TEXT("DECK panel filter discard=1 why=%s"), Why));
  RefreshUmDecks();
}

void AS08FlowGameMode::HandleUmDeckRowInspect(const FString& CardId) {
  // 04 §2.9: a row opens the inspector on the catalog card (the Slate inspector until H13, left of the panel)
  const ES09DeckSide Side = DeckPanel.Side();
  const FS09PlayerPanel* Data = Side == ES09DeckSide::Own ? Hud.ViewerPanel() : Hud.OpponentPanel();
  const FS09DeckList* List = Data ? S09DeckPanel::FindList(DeckLists, Data->PlayerId) : nullptr;
  if (!List) return;
  const FS09DeckPanelModel Model = FS09DeckPanelModel::Build(Side, *Data, List);
  const FS09DeckRow* Row = Model.Rows.FindByPredicate([&CardId](const FS09DeckRow& X) { return X.Card.CardId == CardId; });
  if (!Row) return;
  NoteUmInspectSource(static_cast<uint8>(UmHud.IsValid() && UmHud->DeckBlocks.GetFilter() ? EUmInspectSource::Discard
                                                                                         : EUmInspectSource::DeckRow));
  InspectCard(Row->AsCardView());
  InspectedHandIndex = -1;
  DiscardBrowserIndex = -1;
  InspectedSource = 3;  // the deck panel
  FS08Trace::Write(FString::Printf(TEXT("DECK panel row inspect side=%s"), S09DeckPanel::SideName(Side)));
  RefreshHud();
}

bool AS08FlowGameMode::UmHudCursorOverDeckPanel(float X, float Y) const {
  const UUmHudDeckPanel* Panel = UmHud.IsValid() && UmHud->bLayout ? UmHud->DeckBlocks.GetPanel() : nullptr;
  const float Px = Panel && UmHud->Layout.PxPerSu > 0.0f ? UmHud->Layout.PxPerSu : 1.0f;
  return Panel && Panel->ContainsSu(FVector2D(X / Px, Y / Px));
}

// ------------------------------------------------------------------------------------------------ VS-3 HB-30...HB-33

namespace {
/** The committed card of a combat by its instance id in the viewer's projection (a hidden placeholder stays hidden). */
FS09CardView UmCombatCard(const FS09HudModel& InHud, const FString& InstanceId) {
  FS09CardView Out;
  Out.bHidden = true;
  if (InstanceId.IsEmpty()) return Out;
  for (const FS09PlayerPanel* Panel : {InHud.ViewerPanel(), InHud.OpponentPanel()}) {
    if (!Panel) continue;
    for (const FS09CardView& Card : Panel->Discard) {
      if (Card.InstanceId == InstanceId) return Card;
    }
  }
  return Out;
}
}  // namespace

void AS08FlowGameMode::BuildUmCombat() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  FUmCombatBlocks::FCallbacks C;
  // «Защититься» = Enter, «Без защиты» = N: the same commands (the answer in the frame of the release, UI-INP-011)
  C.OnDefend = [WeakThis](const FS09HudPressOutcome& O) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) {
      Self->HandleHudPressOutcome(O, TFunction<FS09Reason()>(), [WeakThis]() {
        if (AS08FlowGameMode* S = WeakThis.Get()) S->ConfirmCombat();
      });
    }
  };
  C.OnNoDefense = [WeakThis](const FS09HudPressOutcome& O) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) {
      Self->HandleHudPressOutcome(O, TFunction<FS09Reason()>(), [WeakThis]() {
        if (AS08FlowGameMode* S = WeakThis.Get()) S->NoDefenseCommand();
      });
    }
  };
  // 04 §2.7: the right button on a combat card opens the inspector (VS-4 H13: UMG INSPECT; a back - the hidden card)
  C.OnInspect = [WeakThis](const FS09CardView& Card) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self) return;
    Self->NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Combat));
    Self->InspectCard(Card);
    Self->InspectedHandIndex = -1;
    Self->DiscardBrowserIndex = -1;
    Self->RefreshHud();
  };
  ArtHud.PendingTrace.Append(UmHud->Combat.Build(*Game, UmHud->Blocks, HudPress, MoveTemp(C)));
}

bool AS08FlowGameMode::UmCombatOnUmg() const { return UmHud.IsValid() && UmHud->Combat.EdgesOnUmg(); }

bool AS08FlowGameMode::UmCombatCenterOnUmg() const { return UmHud.IsValid() && UmHud->Combat.CenterOnUmg(); }

bool AS08FlowGameMode::UmCombatOwnsDefenseWindow() const {
  return UmCombatOnUmg() && UmHud->Combat.DrawsDefenseWindow() && !S08ArtLook::S08Markers();
}

void AS08FlowGameMode::RefreshUmCombat() {
  if (!UmHud.IsValid() || !UmHud->bLayout || !UmCombatOnUmg()) return;
  FUmHudRuntime& R = *UmHud;
  FUmCombatInput In;
  In.Layout = &R.Layout;
  const bool bAborted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted();
  In.bLive = Hud.bValid && !Hud.bGameOver && !bAborted && !IsResultScreenShown();
  In.ViewerId = ViewerIdNow();
  In.bRu = UmCardMedia::PreferredLang() != TEXT("en");
  In.NowMs = NowMs();
  In.NowSec = FPlatformTime::Seconds();
  In.SpeedMul = CombatSpeedMul();
  In.Stage = &CombatStage;
  const FS08CombatInfo& Combat = CommandUi.Combat;
  In.bResolvePhase = Hud.Phase == TEXT("COMBAT_RESOLVE");
  In.bOpen = Combat.bPresent && (Hud.Phase == TEXT("COMBAT") || In.bResolvePhase);
  In.AppliedSeq = Hud.SequenceNumber;
  In.Combat = Combat;
  // the fighters of the combat shown: the staging's while it runs, else combatInfo's
  const bool bStaged = CombatStage.IsActive();
  const FString AttackerId = bStaged ? CombatStage.GetInput().AttackerId : Combat.AttackerId;
  const FString TargetId = bStaged ? CombatStage.GetInput().TargetId : Combat.TargetFighterId;
  auto Fighter = [this](const FString& Id, const FString& Fallback) {
    FUmCombatFighter Out;
    Out.Id = Id;
    Out.Name = Fallback;
    const FS08BoardFighter* F = Fighters.FindByPredicate([&Id](const FS08BoardFighter& X) { return X.Id == Id; });
    if (!F) return Out;
    Out.Name = F->Label;
    Out.OwnerId = F->OwnerId;
    Out.TeamSlot = BoardActor && BoardActor->TeamOfFighter(*F) == ES08TeamSlot::P2 ? 1 : 0;
    Out.DeckSlug = UmDeckHeroSlug(Fighters, F->OwnerId);
    return Out;
  };
  In.Attacker = Fighter(AttackerId, bStaged ? CombatStage.GetInput().AttackerLabel : FString());
  In.Target = Fighter(TargetId, bStaged ? CombatStage.GetInput().TargetLabel : FString());
  if (In.bOpen) {
    In.AttackCard = UmCombatCard(Hud, Combat.bHasAttackerCard ? Combat.AttackerCardId : FString());
    In.DefenseCard = UmCombatCard(Hud, Combat.bHasDefenderCard ? Combat.DefenderCardId : FString());
  }
  // the own defender in the defense window: the draft, the reasons and the server-anchored deadline (HB-31)
  if (In.bOpen && !In.bResolvePhase && CommandUi.Mode == ES09CommandMode::CombatDefense) {
    In.DraftDefenseId = CommandUi.DefenseCardId;
    In.bHasLegalDefense = !Flow.IsValid() || CommandUi.HasLegalDefenseCard(Flow->GetAppliedSnapshot(), Fighters);
    In.BusyWhy = HudBusyReason();
    if (Combat.bHasTimeoutAt) {
      const FString Key = FString::Printf(TEXT("%lld"), Combat.TimeoutAt.GetTicks());
      if (Key != R.TimerKey) {
        // the snapshot's server time (metadata.lastActionAt); the local clock only when the server sent none
        R.TimerKey = Key;
        FDateTime ServerAt;
        FString At;
        const TSharedPtr<FJsonObject> Meta = Flow.IsValid() && Flow->GetAppliedSnapshot().Metadata.IsValid()
                                                 ? Flow->GetAppliedSnapshot().Metadata->AsObject()
                                                 : nullptr;
        const bool bServer = Meta.IsValid() && Meta->TryGetStringField(TEXT("lastActionAt"), At) && FDateTime::ParseIso8601(*At, ServerAt);
        R.TimerWindowSec = Combat.bHasStartedAt ? static_cast<float>((Combat.TimeoutAt - Combat.StartedAt).GetTotalSeconds()) : 30.0f;
        if (R.TimerWindowSec <= 0.0f) R.TimerWindowSec = 30.0f;
        const double Raw = bServer ? (Combat.TimeoutAt - ServerAt).GetTotalSeconds() : Combat.SecondsUntilDeadline();
        const double Left = FMath::Clamp(Raw, 0.0, static_cast<double>(R.TimerWindowSec));
        R.TimerDeadlineSec = In.NowSec + Left;
        FS08Trace::Write(FString::Printf(TEXT("HUD-TIMER anchor left=%.1f window=%.0f src=%s seq=%d"), Left, R.TimerWindowSec,
                                         bServer ? TEXT("server") : TEXT("local"), Hud.SequenceNumber));
      }
      In.DeadlineSec = R.TimerDeadlineSec;
      In.WindowSec = R.TimerWindowSec;
    }
  }
  if (const UUmHudStatusLine* Status = R.TopStrip.GetStatus()) {
    if (Status->IsShown()) In.StatusBottomSu = static_cast<float>(R.Layout.Rect(EUmHudBlock::Status).Min.Y) + Status->GetBodySizeSu().Y;
  }
  // VS-5 E4 (VS-4 «Открыто» п. 2): the resolve window's button on the own edge (the Slate one gives way)
  In.bResolveButton = In.bOpen && In.bResolvePhase && CommandUi.Mode == ES09CommandMode::CombatResolve && UmHudOwnsSlateBlock(TEXT("resolve"));
  In.ResolveWhy = HudBusyReason().IsSet() ? HudBusyReason() : CommandUi.PendingQueue.Num() > 0 ? FS09Reason::Make(TEXT("why.wait.opponent.choice")) : FS09Reason();
  for (const FString& Line : R.Combat.Refresh(In)) {
    FS08Trace::Write(Line);
    // run I acceptance (AB-8): the auto client frames the first no-defense stamp once its 200 ms appear has landed
    if (Line.StartsWith(TEXT("HUD-STAMP no-defense")) && bAutoS09 && !S09ShotDir.IsEmpty() && ShotStampAtElapsed < 0.0f) {
      ShotStampAtElapsed = Elapsed + 0.25f;
    }
  }
  // ВР-VS3-56: the turn banner never lies over the combat centre - it moves 8 su under the shown panel
  if (UUmHudBanner* Banner = R.TopStrip.GetBanner()) {
    const UUmHudCombatCenter* Center = R.Combat.GetCenter();
    FBox2D Panel = Center && UmGameHudSlots::ShownByProperty(Center) ? Center->PanelRectSu() : FBox2D(ForceInit);
    const FBox2D BannerRect = R.Layout.Rect(EUmHudBlock::Banner);
    // VS-5 E4: an open choice under STATUS (the compact / modal of PENDING) takes the banner under it the same way
    const UUmHudPending* PendingW = R.Pending.Get();
    const FBox2D PendingRect = PendingW && UmGameHudSlots::ShownByProperty(PendingW) && PendingW->GetModel().View != EUmPendingView::Toast
                                   ? PendingW->PanelRectSu() : FBox2D(ForceInit);
    if (PendingRect.bIsValid && BannerRect.bIsValid && PendingRect.Intersect(BannerRect) && (!Panel.bIsValid || PendingRect.Max.Y > Panel.Max.Y)) Panel = PendingRect;
    float Shift = 0.0f;
    if (Panel.bIsValid && BannerRect.bIsValid && Panel.Intersect(BannerRect)) {
      Shift = static_cast<float>(Panel.Max.Y + 8.0 - BannerRect.Min.Y);
    }
    if (!FMath::IsNearlyEqual(Shift, R.BannerShiftSu, 0.5f)) {
      R.BannerShiftSu = Shift;
      Banner->SetRenderTranslation(FVector2D(0.0f, Shift));
      FS08Trace::Write(FString::Printf(TEXT("HUD-BANNER shift=%.0f under=%s"), Shift, Shift > 0.0f ? TEXT("combat") : TEXT("-")));
    }
  }
}

// ------------------------------------------------------------------------------------------------ VS-3 SC-01

void AS08FlowGameMode::TickUmScreenShots() {
  // ВР-SC14 (evidence queue I-03): the first frame of every UI-SCR-* id + state of this run, <UI-ID>-<state>.png in the
  // shot directory; the frame is the evidence queue's (it orders it after a shot in flight)
  if (!UmHud.IsValid() || S09ShotDir.IsEmpty()) return;
  FUmHudRuntime& R = *UmHud;
  if (R.ScreenShots < 0) R.ScreenShots = FParse::Param(FCommandLine::Get(), TEXT("S08ScreenShots")) ? 1 : 0;
  if (R.ScreenShots == 0) return;
  TArray<TPair<FString, FString>> Shown;
  // the GAME screen (UUmGameHud): the state as WriteUmHudShotLines names it
  if (UmHudRoot && UmHudRoot->GetGameHud() && R.Blocks.UmgRoot() && Hud.bValid && !UmFlowScreensCoverLegacy()) {  // VS-7 S3: not under ROOM / LOADING
    const bool bCombat = CommandUi.Combat.bPresent || CombatStage.IsActive();
    const bool bPending = CommandUi.Mode == ES09CommandMode::PendingChoice;
    Shown.Add(TPair<FString, FString>(TEXT("UI-SCR-GAME"), Hud.bGameOver ? TEXT("over")
                                                           : bCombat     ? TEXT("combat")
                                                           : bPending    ? TEXT("pending")
                                                           : Hud.bViewerTurn ? TEXT("own")
                                                                             : TEXT("opp")));
  }
  // every screen / modal built on UUmScreenBase that is shown and fully faded in
  for (const UUmScreenBase* S : UmScreens::LiveScreens()) {
    if (S && S->IsShown() && S->GetAlpha() >= 1.0f && S->GetUiId().StartsWith(TEXT("UI-SCR-"))) {
      Shown.Add(TPair<FString, FString>(S->GetUiId(), S->GetScreenState().ToString()));
    }
  }
  for (const TPair<FString, FString>& P : Shown) {
    const FString Key = P.Key + TEXT("|") + P.Value;
    if (R.ScreenShotKeys.Contains(Key)) continue;
    R.ScreenShotKeys.Add(Key);
    const FString File = UmScreens::ShotFileName(P.Key, P.Value);
    FS08Trace::Write(FString::Printf(TEXT("SCREENSHOT id=%s state=%s file=%s"), *P.Key, *P.Value, *File));
    TakeEvidenceShot(S09ShotDir / File);
    break;  // one request per frame; the next state waits for the next tick
  }
}

// ------------------------------------------------------------------------------------------------ VS-4 HB-35 / HB-37

void AS08FlowGameMode::BuildUmPending() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  FUmHudRuntime& R = *UmHud;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  // every press answers in the frame of its release (UI-INP-011), then the game mode acts
  auto Answer = [WeakThis](const FS09HudPressOutcome& Outcome, TFunction<void(AS08FlowGameMode&)> Act) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) {
      Self->HandleHudPressOutcome(Outcome, TFunction<FS09Reason()>(), [WeakThis, Act]() {
        if (AS08FlowGameMode* S = WeakThis.Get()) Act(*S);
      });
    }
  };
  if (R.Blocks.IsSlate(FName(TEXT("pending")))) {
    ArtHud.PendingTrace.Add(TEXT("HUD-PENDING-UMG impl=slate reason=-S08SlateHud=pending"));
  } else {
    UUmHudPending* P = CreateWidget<UUmHudPending>(Game, UUmHudPending::WidgetClass());
    if (!P || !Game->SetBlock(EUmGameSlot::Pending, P)) {
      ArtHud.PendingTrace.Add(TEXT("HUD-PENDING-UMG impl=umg created=0 reason=create-failed"));
    } else {
      R.Pending = P;
      UUmHudPending::FCallbacks C;
      // «Подтвердить» / «Атаковать с BOOST»: the same command as Enter (the hand-limit discard: its draft)
      C.OnConfirm = [Answer](const FS09HudPressOutcome& O) {
        Answer(O, [](AS08FlowGameMode& S) {
          if (S.CommandUi.Mode == ES09CommandMode::DiscardDraft) {
            S.ConfirmDraft();
          } else {
            S.ConfirmCombat();
          }
        });
      };
      C.OnSecondary = [Answer](const FS09HudPressOutcome& O) { Answer(O, [](AS08FlowGameMode& S) { S.AttackWithoutAbilityBoostCommand(); }); };
      C.OnStay = [Answer](const FS09HudPressOutcome& O) { Answer(O, [](AS08FlowGameMode& S) { S.StayPendingInPlaceCommand(); }); };
      C.OnDecline = [Answer](const FS09HudPressOutcome& O) { Answer(O, [](AS08FlowGameMode& S) { S.DeclinePendingChoiceCommand(); }); };
      C.OnBack = [Answer](const FS09HudPressOutcome& O) { Answer(O, [](AS08FlowGameMode& S) { S.UmPendingEscape(); }); };
      C.OnToggle = [Answer](const FS09HudPressOutcome& O) { Answer(O, [](AS08FlowGameMode& S) { S.TogglePendingCollapseCommand(); }); };
      C.OnOption = [Answer](const FS09HudPressOutcome& O, int32 Index) {
        Answer(O, [Index](AS08FlowGameMode& S) {
          FString Reason;
          const bool bOk = S.CommandUi.SelectPendingOption(Index, Reason);
          FS08Trace::Write(FString::Printf(TEXT("HUD-PENDING option=%d ok=%d"), Index, bOk ? 1 : 0));
          if (!bOk) {
            S.Toast = TEXT("option rejected: ") + Reason;
            S.ToastUntil = S.Elapsed + 3.0f;
          }
          S.RefreshHud();
        });
      };
      C.OnCard = [Answer](const FS09HudPressOutcome& O, const FString& InstanceId) {
        Answer(O, [InstanceId](AS08FlowGameMode& S) {
          FString Reason;
          const bool bOk = S.CommandUi.TogglePendingCard(InstanceId, S.EffectiveSnapshot(), Reason);
          FS08Trace::Write(FString::Printf(TEXT("HUD-PENDING card toggle ok=%d picked=%d"), bOk ? 1 : 0, S.CommandUi.PendingCardIds.Num()));
          if (!bOk) {
            S.Toast = TEXT("pick rejected: ") + Reason;
            S.ToastUntil = S.Elapsed + 3.0f;
          }
          S.RefreshHud();
        });
      };
      // no MVP card asks for a number (ВР-HB11): a step is answered and traced only
      C.OnStep = [Answer](const FS09HudPressOutcome& O, int32 Delta) {
        Answer(O, [Delta](AS08FlowGameMode&) { FS08Trace::Write(FString::Printf(TEXT("HUD-PENDING number step=%d"), Delta)); });
      };
      C.OnInspect = [WeakThis](const FS09CardView& Card) {
        AS08FlowGameMode* Self = WeakThis.Get();
        if (!Self || Card.bHidden) return;
        Self->NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Pending));
        Self->InspectCard(Card);
        Self->InspectedHandIndex = -1;
        Self->DiscardBrowserIndex = -1;
        Self->RefreshHud();
      };
      P->SetInput(HudPress, MoveTemp(C));
      FString Missing;
      ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-PENDING-UMG impl=umg created=1 source=%s parts=%d missing=%s"),
                                              *P->WidgetSourceName(), P->HasAllParts(&Missing) ? 1 : 0,
                                              Missing.IsEmpty() ? TEXT("-") : *Missing));
    }
  }
  if (R.Blocks.IsSlate(FName(TEXT("slot")))) {
    ArtHud.PendingTrace.Add(TEXT("HUD-SLOT-UMG impl=slate reason=-S08SlateHud=slot"));
    return;
  }
  UUmHudSourceSlot* W = CreateWidget<UUmHudSourceSlot>(Game, UUmHudSourceSlot::WidgetClass());
  if (!W || !Game->SetBlock(EUmGameSlot::SourceSlot, W)) {
    ArtHud.PendingTrace.Add(TEXT("HUD-SLOT-UMG impl=umg created=0 reason=create-failed"));
    return;
  }
  R.Slot = W;
  FString Missing;
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-SLOT-UMG impl=umg created=1 source=%s parts=%d missing=%s"), *W->SourceName(),
                                          W->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
}

bool AS08FlowGameMode::UmPendingOwnsCommandPanel() const {
  return UmHud.IsValid() && UmHud->Pending.IsValid() && !S08ArtLook::S08Markers();
}

bool AS08FlowGameMode::UmSlotOnUmg() const { return UmHud.IsValid() && UmHud->Slot.IsValid(); }

FString AS08FlowGameMode::UmPendingSourceName() const {
  if (!UmHud.IsValid() || !CommandUi.bHasPendingChoice || UmHud->PendingHeadId != CommandUi.PendingChoice.Id) return FString();
  return UmHud->PendingTitle;
}

bool AS08FlowGameMode::UmPendingEscape() {
  // 04 §2.8 / HB-35 p. 4: Esc - «Назад» when the open own choice has one, why.choice.required (CUE-004) when it is
  // mandatory; an optional choice without a step back keeps the old Esc (the selection clears)
  if (!UmHud.IsValid() || !UmHud->Pending.IsValid() || CommandUi.Mode != ES09CommandMode::PendingChoice ||
      !CommandUi.bHasPendingChoice) {
    return false;
  }
  const UUmHudPending* P = UmHud->Pending.Get();
  if (P->GetModel().bBack) {
    // CHOOSE_ONE: the picked option goes (the command did not leave: no busy state, ВР-VS4-07)
    CommandUi.PendingOptionIndex = -1;
    FS08Trace::Write(FString::Printf(TEXT("HUD-PENDING back id=%s"), *CommandUi.PendingChoice.Id));
    RefreshHud();
    return true;
  }
  if (!CommandUi.PendingChoice.bOptional) {
    FS08Trace::Write(FString::Printf(TEXT("HUD-PENDING esc refused id=%s why=why.choice.required"), *CommandUi.PendingChoice.Id));
    ShowReason(FS09Reason::Make(TEXT("why.choice.required")), 3.0f);
    return true;
  }
  return false;
}

void AS08FlowGameMode::RefreshUmPending() {
  if (!UmHud.IsValid() || !UmHud->bLayout) return;
  FUmHudRuntime& R = *UmHud;
  UUmHudPending* P = R.Pending.Get();
  if (!P) return;
  UmHudPending::FUmPendingInput In;
  const bool bAborted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted();
  In.bLive = Flow.IsValid() && Hud.bValid && !Hud.bGameOver && !bAborted && !IsResultScreenShown();
  In.ViewerId = ViewerIdNow();
  In.Ui = &CommandUi;
  In.Presenter = &PendingPresenter;
  In.bCombatStaging = CombatStage.IsActive();
  In.bHeldBySlot = CardSlot.HoldsEffect() &&
                   (CommandUi.Mode == ES09CommandMode::PendingChoice || CommandUi.Mode == ES09CommandMode::DiscardDraft);
  const UUmHudStatusLine* Status = R.TopStrip.GetStatus();
  In.bStatusSaysOpp = Status && Status->IsShown() && !UmHudBlockOnSlate(TEXT("status"));
  In.BusyWhy = HudBusyReason();
  In.bRu = UmCardMedia::PreferredLang() != TEXT("en");
  // the source card: the catalog cards of both deck lists (gameDeckLists, public), the own hand and both piles
  for (const FS09DeckList& List : DeckLists) {
    for (const FS09DeckListCard& Card : List.Cards) {
      FS09CardView V;
      V.CardId = Card.CardId;
      V.Name = Card.Name;
      V.NameRu = Card.NameRu;
      V.CardType = Card.CardType;
      V.Text = Card.Text;
      V.BannerName = Card.BannerName;
      In.Known.Add(V);
    }
  }
  for (const FS09PlayerPanel* Panel : {Hud.ViewerPanel(), Hud.OpponentPanel()}) {
    if (!Panel) continue;
    In.HeroNames.Add(Panel->PlayerId, PlayerHeroName(Panel->PlayerId));
    In.Known.Append(Panel->Cards);
    In.Known.Append(Panel->Discard);
  }
  const FS08PendingEffect* Head = CommandUi.Mode == ES09CommandMode::PendingChoice && CommandUi.bHasPendingChoice
                                      ? &CommandUi.PendingChoice
                                      : (CommandUi.PendingQueue.Num() > 0 ? &CommandUi.PendingQueue[0] : nullptr);
  if (Head) {
    for (const FS09PlayerPanel* Panel : {Hud.ViewerPanel(), Hud.OpponentPanel()}) {
      if (Panel && Panel->PlayerId == Head->PlayerId) In.OwnerDiscard = Panel->Discard;
    }
  }
  if (const FS09PlayerPanel* Own = Hud.ViewerPanel()) In.OwnHeroSlug = UmDeckHeroSlug(Fighters, Own->PlayerId);
  if (CommandUi.Mode == ES09CommandMode::PendingChoice && Flow.IsValid()) {
    const FS08Snapshot& Snap = EffectiveSnapshot();
    const FS09PendingMovePrompt Move = CommandUi.DescribePendingMovePlace(BoardModel, Fighters);
    if (Move.bValid) {
      In.MovePrompt = Move.Prompt;
      In.bCanStay = Move.bCanStay;
    }
    TArray<FString> Pool;
    int32 Need = 0;
    if (CommandUi.PendingCardPickPlan(Snap, Pool, Need)) In.PickNeed = Need;
    CommandUi.PendingRevealedCards(In.Revealed);
    // the toast's «В прошлый раз: {choice}»: the fighter, else the space, else the option - as the UI names them
    if (const FS09PendingVariant* Last = PendingPresenter.Remembered()) {
      if (!Last->FighterId.IsEmpty()) {
        if (const FS08BoardFighter* F = FindFighter(Last->FighterId)) In.RememberedChoice = F->Label.IsEmpty() ? F->Name : F->Label;
      }
      if (In.RememberedChoice.IsEmpty() && Last->bHasCell) In.RememberedChoice = BoardModel.CellLabel(Last->CellX, Last->CellY);
      if (In.RememberedChoice.IsEmpty() && Last->OptionIndex >= 0) {
        for (const FS08PendingOption& O : CommandUi.PendingChoice.Options) {
          if (O.Index == Last->OptionIndex) In.RememberedChoice = O.Label;
        }
      }
    }
  }
  const FUmPendingModel M = UmHudPending::Gather(In);
  R.PendingHeadId = M.HeadId;
  R.PendingTitle = M.Title;
  // ---- the frame: CENTER, under a shown STATUS and a shown combat centre (ВР-VS4-06) ----
  FUmPendingFrame F;
  F.bClassS = R.Layout.bClassS;
  F.PxPerSu = R.Layout.PxPerSu;
  F.CanvasSu = R.Layout.CanvasSu;
  const FBox2D Center = R.Layout.Rect(EUmHudBlock::Center);
  float Top = Center.bIsValid ? static_cast<float>(Center.Min.Y) : (F.bClassS ? 64.0f : 80.0f);
  if (Status && Status->IsShown()) {
    Top = FMath::Max(Top, static_cast<float>(R.Layout.Rect(EUmHudBlock::Status).Min.Y) + static_cast<float>(Status->GetBodySizeSu().Y) + 8.0f);
  }
  if (const UUmHudCombatCenter* Centre = R.Combat.GetCenter()) {
    if (UmGameHudSlots::ShownByProperty(Centre) && M.View != EUmPendingView::Modal) {
      const FBox2D CR = Centre->PanelRectSu();
      if (CR.bIsValid) Top = FMath::Max(Top, static_cast<float>(CR.Max.Y) + 8.0f);
    }
  }
  F.TopSu = Top;
  F.ModalWidthSu = F.bClassS ? 560.0f : 640.0f;
  F.ModalCapSu = F.bClassS ? 360.0f : (R.Layout.bTall ? 420.0f : 380.0f);
  const FBox2D SlotRect = R.Layout.Rect(EUmHudBlock::SourceSlot);
  F.BandLeftSu = SlotRect.bIsValid ? static_cast<float>(SlotRect.Max.X) + 8.0f : 0.0f;
  float Right = static_cast<float>(R.Layout.CanvasSu.X);
  for (const EUmHudBlock B : {EUmHudBlock::PanelOpp, EUmHudBlock::OppHand}) {
    if (R.Layout.HasRect(B)) Right = FMath::Min(Right, static_cast<float>(R.Layout.Rect(B).Min.X));
  }
  F.BandRightSu = Right - 8.0f;
  if (M.View == EUmPendingView::Toast && R.Feed.ToastOnUmg()) {
    // VS-4 HB-36 (ВР-VS4-27): a member of the toast stack - the stack's chain places it (TickUmFeed), it waits hidden
    // until it has a place
    F.ToastSu = R.Feed.PendingToastRect();
    F.bToastWaits = !F.ToastSu.bIsValid;
  } else if (M.View == EUmPendingView::Toast) {
    // ВР-H06: over the hand caption, or the top strip when it would cross a figure (the stack rule of the toasts)
    const float PxPerSu = HudPixelsPerUnit() > 0.0f ? HudPixelsPerUnit() : R.Layout.PxPerSu;
    TArray<FBox2D> Avoid;
    for (const TPair<FString, FS08ScreenRect>& Fig : FigureScreenRects()) Avoid.Add(UmHudPxToSu(Fig.Value, PxPerSu));
    bool bTop = false;
    const FBox2D Caption = R.Layout.Rect(EUmHudBlock::HandCaption);
    F.ToastSu = R.Layout.StackRect(EUmHudBlock::Toast, UmHudPending::ToastWidthSu(F.bClassS, R.Layout.bTall), UmHudPending::ToastHSu,
                                   0.0f, 0.0f, Avoid, bTop, Caption.bIsValid ? static_cast<float>(Caption.Min.Y) : -1.0f);
  }
  P->SetFrame(F);
  P->ApplyModel(M);
  const FString Line = P->TakeChangeLine();
  if (!Line.IsEmpty() && FS08Trace::IsOpen()) FS08Trace::Write(FString::Printf(TEXT("%s seq=%d"), *Line, Hud.SequenceNumber));
}

void AS08FlowGameMode::TickUmSourceSlot() {
  if (!UmSlotOnUmg() || !UmHud->bLayout) return;
  FUmHudRuntime& R = *UmHud;
  UUmHudSourceSlot* W = R.Slot.Get();
  FUmSlotFrame Frame;
  Frame.bClassS = R.Layout.bClassS;
  Frame.PxPerSu = R.Layout.PxPerSu;
  Frame.CardSu = R.Layout.Rect(EUmHudBlock::SourceSlot);
  const FBox2D SlotRect = UmGameHudSlots::SlotRect(R.Layout, EUmGameSlot::SourceSlot);
  Frame.OriginSu = SlotRect.bIsValid ? FVector2D(SlotRect.Min) : FVector2D(Frame.CardSu.Min);
  W->SetFrame(Frame);
  const int64 Now = NowMs();
  const FS09SlotCard& C = CardSlot.GetCard();
  FUmSlotModel M;
  M.bShow = CardSlot.IsVisible() && Hud.bValid && !IsResultScreenShown();
  M.Revision = CardSlot.GetRevision();
  M.Seq = C.Seq;
  M.Phase = UmHudSourceSlot::PhaseOf(CardSlot.GetState());
  M.Card = C.Card;
  M.bFace = !C.Card.bHidden && !C.Card.Name.IsEmpty();
  M.HeroSlug = UmDeckHeroSlug(Fighters, C.OwnerId);
  M.Ribbon = C.Ribbon;
  M.bOpponent = C.bOpponent;
  M.OwnerName = PlayerHeroName(C.OwnerId);
  M.Boost = C.Ribbon == ES09SlotRibbon::Boosted && C.Card.bHasBoostValue ? C.Card.BoostValue : UmCardWidget::NoBoostChip;
  M.FlyT = CardSlot.FlyT(Now);
  if (CardSlot.HoldsEffect() && CardSlot.GetState() == ES09SlotState::Hold) {
    const double Left = static_cast<double>(CardSlot.ReleaseAtMs() - Now);
    M.HoldFrac = FMath::Clamp(1.0f - static_cast<float>(Left / FS09SourceSlot::OppSchemeHoldMs), 0.0f, 1.0f);
  }
  // a new card: where it flies from (ВР-VS4-12) - the own card from where the hand drew it (the hand drops its own
  // flight), the opponent's from OPP-HAND
  if (M.bShow && M.Revision != R.SlotRevision) {
    R.SlotRevision = M.Revision;
    FVector2D From = FVector2D::ZeroVector;
    bool bHanded = false;
    if (C.bOpponent) {
      const FBox2D Opp = R.Layout.Rect(EUmHudBlock::OppHand);
      if (Opp.bIsValid) From = Opp.GetCenter();
    } else {
      FBox2D Handed(ForceInit);
      UUmHudHand* Hand = R.Hand.Get();
      if (Hand && Hand->HandOffCard(C.Card.InstanceId, Handed)) {
        From = Handed.GetCenter();
        bHanded = true;
      } else if (R.Layout.HasRect(EUmHudBlock::Hand)) {
        From = R.Layout.Rect(EUmHudBlock::Hand).GetCenter();
      }
    }
    R.SlotFlyFrom = From;
    FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT-UMG card seq=%d ribbon=%s owner=%s face=%d from=(%.0f,%.0f) handoff=%d"), C.Seq,
                                     S09SlotRibbonName(C.Ribbon), C.bOpponent ? TEXT("opp") : TEXT("own"), M.bFace ? 1 : 0, From.X,
                                     From.Y, bHanded ? 1 : 0));
  }
  M.FlyFromSu = R.SlotFlyFrom;
  M.SpeedMul = CombatSpeedMul();  // VS-4 CP-21: the played flash x UI-ACC-013
  W->ApplyModel(M);
  UmNoteCardFlashes(W->TakePlayedFlashes(), C.Seq);
  const FString Line = W->TakeChangeLine();
  if (!Line.IsEmpty()) FS08Trace::Write(Line);
}

// ------------------------------------------------------------------------------------------------ VS-4 HB-39...HB-41

void AS08FlowGameMode::BuildUmFeed() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  FUmFeedBlocks::FCallbacks C;
  // a sticky toast's cross answers in the frame of its release (UI-INP-011); the hand-limit rule closes through its
  // owner (FS09HandLimitHint: close=click in the trace), any other sticky toast leaves
  C.OnToastClose = [WeakThis](const FS09HudPressOutcome& O, FName Key) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self) return;
    Self->HandleHudPressOutcome(O, TFunction<FS09Reason()>(), [WeakThis, Key]() {
      AS08FlowGameMode* S = WeakThis.Get();
      if (!S) return;
      if (Key == FName(TEXT("ms.hint.hand.limit"))) {
        S->DismissHandLimitHint();
      } else if (S->UmHud.IsValid()) {
        S->UmHud->Feed.DismissToast(Key, static_cast<double>(S->NowMs()));
      }
    });
  };
  C.OnLogInspect = [WeakThis](const FString& CardId) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmLogInspect(CardId);  // VS-4 H13: either deck list
  };
  ArtHud.PendingTrace.Append(UmHud->Feed.Build(*Game, UmHud->Blocks, HudPress, MoveTemp(C)));
}

void AS08FlowGameMode::TickUmFeed() {
  if (!UmHud.IsValid() || !UmHud->bLayout) return;
  FUmHudRuntime& R = *UmHud;
  const double Now = static_cast<double>(NowMs());
  const bool bAborted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted();
  const float PxPerSu = R.Layout.PxPerSu > 0.0f ? R.Layout.PxPerSu : 1.0f;
  // the turn of each applied seq (the log's «Х{n}»: the turn the event happened in)
  if (Hud.bValid && (R.SeqTurns.Num() == 0 || R.SeqTurns.Last().Seq != Hud.SequenceNumber)) {
    FUmHudRuntime::FSeqTurn T;
    T.Seq = Hud.SequenceNumber;
    T.Turn = Hud.TurnCount;
    const FS09PlayerPanel* TurnPanel = Hud.bViewerTurn ? Hud.ViewerPanel() : Hud.OpponentPanel();
    T.Player = TurnPanel ? TurnPanel->PlayerId : FString();
    R.SeqTurns.Add(T);
    if (R.SeqTurns.Num() > 256) R.SeqTurns.RemoveAt(0, R.SeqTurns.Num() - 256);
  }
  // «Позиции обновлены (пропущено {n})» (04 §1.9, §2.12): the stream came back after a loss; n = the seqs the
  // snapshot jumped over
  const bool bStarted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started;
  const bool bRecovering = bStarted && (Flow->IsAwaitingStateRecovery() || !Flow->IsStreamReady());
  if (bStarted && !bRecovering && Hud.bValid) R.bStreamSeenReady = true;
  if (bRecovering && R.bStreamSeenReady && !R.bReconnecting) {
    R.bReconnecting = true;
    R.ReconnectSeq = Hud.SequenceNumber;
  } else if (!bRecovering && R.bReconnecting) {
    R.bReconnecting = false;
    const int32 Missed = FMath::Max(0, Hud.SequenceNumber - R.ReconnectSeq);
    // VS-4 HB-49: leaving the room while recovering (abort, result) is not a reconnect - no toast (it stuck in the lobby)
    const bool bDue = UmHudFeed::ReconnectedToastDue(bStarted, Hud.bValid, bAborted);
    if (R.Feed.ToastOnUmg() && bDue) {
      FUmToastSpec Spec;
      Spec.Kind = EUmToastKind::Info;
      FFormatNamedArguments Args;
      Args.Add(TEXT("n"), FText::FromString(FString::FromInt(Missed)));
      Spec.Text = UmText::Format(EUmTable::Hud, TEXT("hud.toast.reconnected"), Args);
      Spec.Key = FName(TEXT("hud.toast.reconnected"));
      Spec.HoldSec = 3.0f;
      R.Feed.PushToast(Spec, Now);
    }
    FS08Trace::Write(FString::Printf(TEXT("TOAST hud=hud.toast.reconnected missed=%d seqBefore=%d seq=%d shown=%d"), Missed,
                                     R.ReconnectSeq, Hud.SequenceNumber, bDue ? 1 : 0));
  }
  // class S: the open list closes on a click outside it (not on «Журнал» itself - its press toggles) or Esc
  if (R.Feed.IsLogOpen()) {
    APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    float MX = -1.0f, MY = -1.0f;
    const bool bMouse = PC && PC->GetMousePosition(MX, MY);
    const FVector2D P(MX / PxPerSu, MY / PxPerSu);
    const bool bClick = PC && (PC->WasInputKeyJustPressed(EKeys::LeftMouseButton) || PC->WasInputKeyJustPressed(EKeys::RightMouseButton));
    const bool bInside = bMouse && (R.Feed.LogListRectSu().IsInside(P) || R.Layout.Rect(EUmHudBlock::Top).IsInside(P));
    if ((bClick && !bInside) || (PC && PC->WasInputKeyJustPressed(EKeys::Escape))) {
      R.Feed.SetLogOpen(false);
      FS08Trace::Write(TEXT("HUD-LOG list close=input"));
    }
  }
  // ---- the input of the placement ----
  FUmFeedInput In;
  In.Layout = &R.Layout;
  In.bLive = Hud.bValid && !Hud.bGameOver && !bAborted && !IsResultScreenShown();
  In.NowMs = Now;
  In.bReduced = MoveMotion.bReducedMotion;
  In.bCombat = CommandUi.Combat.bPresent || CombatStage.IsActive();
  const UUmHudBanner* Banner = R.TopStrip.GetBanner();
  In.bBannerShown = Banner && Banner->GetAlpha() > 0.0f;
  const UUmHudStatusLine* Status = R.TopStrip.GetStatus();
  if (Status && Status->IsShown() && R.Layout.HasRect(EUmHudBlock::Status)) {
    In.StatusBottomSu = static_cast<float>(R.Layout.Rect(EUmHudBlock::Status).Min.Y) + static_cast<float>(Status->GetBodySizeSu().Y);
  }
  for (const TPair<FString, FS08ScreenRect>& F : FigureScreenRects()) In.Figures.Add(UmHudPxToSu(F.Value, PxPerSu));
  for (const FS08ArtHudRuntime::FTagSlot& Tag : ArtHud.Tags) {
    if (Tag.bShown && !Tag.Planned.IsEmpty()) In.Figures.Add(UmHudPxToSu(Tag.Planned, PxPerSu));
  }
  if (ArtHud.bPlateVisible && !ArtHud.PlatePlanned.IsEmpty()) In.Figures.Add(UmHudPxToSu(ArtHud.PlatePlanned, PxPerSu));
  In.Spaces = R.SpaceRectsSu;
  // every drawn HUD block (04 §2.12): the persistent ones at their rects, the others as drawn now
  auto Shown = [](const UWidget* W) { return UmGameHudSlots::ShownByProperty(W); };
  if (Shown(R.TopStrip.GetTop())) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::Top));
  if (In.StatusBottomSu > 0.0f) {
    const FBox2D& St = R.Layout.Rect(EUmHudBlock::Status);
    const float W = static_cast<float>(Status->GetBodySizeSu().X);
    const float X = static_cast<float>(St.GetCenter().X) - 0.5f * W;
    In.Blocks.Add(FBox2D(FVector2D(X, St.Min.Y), FVector2D(X + W, In.StatusBottomSu)));
  }
  if (Shown(R.Panels.GetLoc())) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::PanelLoc));
  if (Shown(R.Panels.GetOpp())) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::PanelOpp));
  if (Shown(R.Panels.GetOppHand())) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::OppHand));
  if (R.Layout.HasRect(EUmHudBlock::Decks)) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::Decks));
  if (R.Layout.HasRect(EUmHudBlock::Actions)) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::Actions));
  if (const UUmHudLog* LogW = R.Feed.GetLog()) {
    if (!R.Layout.bClassS && Shown(LogW)) In.Blocks.Add(R.Layout.Rect(EUmHudBlock::Log));
  }
  if (const UUmHudSourceSlot* SlotW = R.Slot.Get()) {
    if (SlotW->GetPhase() != EUmSlotPhase::Hidden) In.Blocks.Add(SlotW->DrawnRectSu());
  }
  if (const UUmHudPending* P = R.Pending.Get()) {
    if (Shown(P) && P->GetModel().View != EUmPendingView::Toast) In.Blocks.Add(P->PanelRectSu());
    if (P->GetModel().View == EUmPendingView::Toast) {
      const FUmPendingPlan& Plan = P->GetPlan();
      const float H = Plan.Panel.bIsValid ? FMath::Max(48.0f, static_cast<float>(Plan.Panel.GetSize().Y)) : 48.0f;
      In.PendingToastSu = FVector2D(UmHudPending::ToastWidthSu(R.Layout.bClassS, R.Layout.bTall), H);
    }
  }
  if (const UUmHudCombatCenter* Centre = R.Combat.GetCenter()) {
    if (Shown(Centre)) In.Blocks.Add(Centre->PanelRectSu());
  }
  for (const EUmEdgeSide Side : {EUmEdgeSide::Own, EUmEdgeSide::Opp}) {
    const UUmHudCombatEdge* E = R.Combat.GetEdge(Side);
    if (!Shown(E)) continue;
    In.Blocks.Add(UmGameHudSlots::SlotRect(R.Layout, Side == EUmEdgeSide::Own ? EUmGameSlot::CombatEdgeL : EUmGameSlot::CombatEdgeR));
  }
  // the Slate panels that still draw (the command panel's buttons until ACTIONS, the hand panel's lines, the side panel)
  for (const TWeakPtr<SWidget>& Weak : {ArtHud.CommandPanel, ArtHud.HandPanel, ArtHud.SidePanel}) {
    const TSharedPtr<SWidget> W = Weak.Pin();
    FS08ScreenRect Px;
    if (W.IsValid() && W->GetVisibility().IsVisible() && W->GetRenderOpacity() > 0.0f && WidgetViewportRect(W, Px) && !Px.IsEmpty()) {
      In.Blocks.Add(UmHudPxToSu(Px, PxPerSu));
    }
  }
  // the hand: the cards as drawn now (the lowering included, not the hover preview), the caption plate
  if (const UUmHudHand* Hand = R.Hand.Get()) {
    const UmHudHand::FRow& Row = Hand->GetRow();
    if (Shown(Hand) && Row.CardPos.Num() > 0) {
      const float Lower = Hand->GetLowerNowSu();
      FBox2D Cards(ForceInit);
      for (const FVector2D& Pos : Row.CardPos) {
        Cards += FBox2D(FVector2D(Pos.X, Pos.Y + Lower),
                        FVector2D(Pos.X + Row.CardSize.X, FMath::Min(R.Layout.CanvasSu.Y, Pos.Y + Lower + Row.CardSize.Y)));
      }
      if (Cards.bIsValid) {
        In.Blocks.Add(Cards);
        In.CardsTopSu = static_cast<float>(Cards.Min.Y);
      }
      if (Hand->IsCaptionShown()) In.CaptionSu = Hand->CaptionRectSu();
      In.bHandLowered = Lower > 0.5f;
    }
  }
  for (const FString& Line : R.Feed.Refresh(In)) FS08Trace::Write(Line);
  // VS-5 E4 (VS-4 «Открыто» п. 5): the same blocks are the world tags' and the plate's obstacles (px)
  UmHudBlocksPx.Reset();
  for (const FBox2D& B : In.Blocks) {
    UmHudBlocksPx.Add(FS08ScreenRect(static_cast<float>(B.Min.X) * PxPerSu, static_cast<float>(B.Min.Y) * PxPerSu,
                                     static_cast<float>(B.Max.X) * PxPerSu, static_cast<float>(B.Max.Y) * PxPerSu));
  }
  // HB-36: the pending trigger toast follows the stack's placement
  const FBox2D PendingRect = R.Feed.PendingToastRect();
  if (PendingRect.bIsValid != R.PendingToastRect.bIsValid || (PendingRect.bIsValid && !(PendingRect == R.PendingToastRect))) {
    R.PendingToastRect = PendingRect;
    RefreshUmPending();
  }
}

void AS08FlowGameMode::UmHudLogTrail(const FS09LastMovement& Trail, const FString& CardName, const TArray<FString>& YourFighters) {
  if (!UmHud.IsValid() || !UmHud->Feed.LogOnUmg()) return;
  FUmHudRuntime& R = *UmHud;
  const bool bRu = UmCardMedia::PreferredLang() != TEXT("en");
  // a card of the public piles by its name: the UI language's title and its id (the click opens the inspector)
  auto FindCard = [this](const FString& Name) -> const FS09CardView* {
    if (Name.IsEmpty()) return nullptr;
    for (const FS09PlayerPanel* Panel : {Hud.ViewerPanel(), Hud.OpponentPanel()}) {
      if (!Panel) continue;
      for (const FS09CardView& C : Panel->Discard) {
        if (!C.bHidden && (C.Name == Name || C.NameRu == Name)) return &C;
      }
    }
    return nullptr;
  };
  auto Title = [bRu](const FS09CardView* C, const FString& Fallback) {
    return C && bRu && !C->NameRu.IsEmpty() ? C->NameRu : (C ? C->Name : Fallback);
  };
  FUmLogEntry E;
  E.Seq = Trail.Seq;
  // «Х{n}»: the turn of the acting player at the event's seq (a turn-ending snapshot may already name the next turn)
  for (int32 I = R.SeqTurns.Num() - 1; I >= 0 && E.Turn == 0; --I) {
    if (R.SeqTurns[I].Seq <= Trail.Seq && R.SeqTurns[I].Player == Trail.PlayerId) E.Turn = R.SeqTurns[I].Turn;
  }
  for (int32 I = R.SeqTurns.Num() - 1; I >= 0 && E.Turn == 0; --I) {
    if (R.SeqTurns[I].Seq <= Trail.Seq) E.Turn = R.SeqTurns[I].Turn;
  }
  // the stripe: the acting player's team as the board draws it (absolute or -S08TeamColorMode relative)
  const FString ViewerId = ViewerIdNow();
  const FS08BoardFighter* Mover = Trail.Moves.Num() > 0 ? FindFighter(Trail.Moves[0].FighterId) : nullptr;
  if (!Mover) Mover = Fighters.FindByPredicate([&Trail](const FS08BoardFighter& F) { return F.OwnerId == Trail.PlayerId; });
  if (Mover && BoardActor) {
    E.TeamSlot =
        S08TeamLook(BoardActor->TeamOfFighter(*Mover), Mover->OwnerId == ViewerId, BoardActor->GetTeamColorMode()) == ES08TeamSlot::P2 ? 1 : 0;
  }
  const bool bEffect = Trail.Source == TEXT("EFFECT");
  const FS09CardView* Card = FindCard(bEffect ? CardName : Trail.BoostName);
  FS09LastMovement Shown = Trail;
  if (Trail.bBoost) Shown.BoostName = Title(Card, Trail.BoostName);
  const FString ShownCard = bEffect ? Title(Card, CardName) : CardName;
  if (Card) E.CardId = Card->CardId;
  UmHudLog::DescribeTrail(
      Shown, ShownCard, YourFighters, [this](const FString& Id) { return PlayerHeroName(Id); },
      [this](const FString& Id) -> FString {
        const FS08BoardFighter* F = FindFighter(Id);
        return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : Id;
      },
      [this](const FIntPoint& Cell) { return BoardModel.CellLabel(Cell.X, Cell.Y); }, E.Text, E.Full, &E.Shorter);
  R.Feed.PushLog(E, static_cast<double>(NowMs()));
  FS08Trace::Write(FString::Printf(TEXT("HUD-LOG add seq=%d turn=%d team=%d card=%d total=%d"), E.Seq, E.Turn, E.TeamSlot,
                                   E.CardId.IsEmpty() ? 0 : 1, R.Feed.GetLog() ? R.Feed.GetLog()->Num() : 0));
}

void AS08FlowGameMode::UmHudToastReason(const FS09Reason& Reason, float Seconds) {
  if (!UmHud.IsValid() || !UmHud->Feed.ToastOnUmg() || !Reason.IsSet()) return;
  FUmToastSpec Spec;
  Spec.Kind = UmHudFeed::KindOfKey(Reason.Key);
  Spec.Text = UmHudFeed::ReasonText(Reason);
  Spec.HoldSec = Seconds;
  Spec.Key = Reason.Key;
  UmHud->KeyedToastEn = Reason.Text();
  UmHud->Feed.PushToast(Spec, static_cast<double>(NowMs()));
}

FString AS08FlowGameMode::UmHudSlateToast(const FString& Shown) const {
  if (UmHudBlockOnSlate(TEXT("toast")) || !UmHud->Feed.ToastOnUmg()) return Shown;  // the rollback: the old line
  // the default view: the keyed toasts are UMG; the non-keyed developer strings stay in the gate layer only (ВР-VS4-26)
  if (!S08ArtLook::S08Markers() || Shown == UmHud->KeyedToastEn) return FString();
  return Shown;
}

bool AS08FlowGameMode::UmHudShowSubtitle(const FString& SpeakerName, const FString& Line, int64 DurationMs) {
  if (!UmHud.IsValid() || !UmHud->Feed.SubOnUmg()) return false;
  FUmSubtitleModel M;
  M.Speaker = UmHudSubtitle::SpeakerText(SpeakerName);
  M.Line = FText::FromString(Line);
  M.StartMs = static_cast<double>(NowMs());
  M.DurationMs = static_cast<double>(DurationMs);
  UmHud->Feed.ShowSubtitle(M);
  FS08Trace::Write(FString::Printf(TEXT("HUD-SUB show speaker=%d ms=%lld"), SpeakerName.IsEmpty() ? 0 : 1, static_cast<long long>(DurationMs)));
  return true;
}

void AS08FlowGameMode::UmHudHideSubtitle() {
  if (UmHud.IsValid()) UmHud->Feed.HideSubtitle();
}

bool AS08FlowGameMode::UmHudSyncHandLimit() {
  if (!UmHud.IsValid() || !UmHud->Feed.ToastOnUmg()) return false;
  const FName Key(TEXT("ms.hint.hand.limit"));
  UUmToastStack* T = UmHud->Feed.GetToasts();
  const double Now = static_cast<double>(NowMs());
  if (HandLimitHint.IsVisible() && T && !T->Has(Key)) {
    // DE-024: the rule toast, held until its cross, the end of the turn or GAME_OVER (FS09HandLimitHint)
    FUmToastSpec Spec;
    Spec.Kind = EUmToastKind::Warning;
    FFormatNamedArguments Args;
    Args.Add(TEXT("n"), FText::FromString(FString::FromInt(HandLimitHint.ShownLimit())));
    Spec.Text = UmText::Format(EUmTable::Ms, Key.ToString(), Args);
    Spec.Key = Key;
    Spec.bSticky = true;
    UmHud->Feed.PushToast(Spec, Now);
  } else if (!HandLimitHint.IsVisible() && T && T->Has(Key)) {
    UmHud->Feed.DismissToast(Key, Now);
  }
  return true;
}

void AS08FlowGameMode::UmHudRefuseCell(int32 CellX, int32 CellY) {
  if (!UmHud.IsValid() || !UmHud->Feed.ToastOnUmg() || !UmHud->bLayout) return;
  FVector2D Screen(0.0, 0.0);
  if (!ProjectToViewport(BoardModel.CellToWorld(CellX, CellY), Screen)) return;
  const float Px = UmHud->Layout.PxPerSu > 0.0f ? UmHud->Layout.PxPerSu : 1.0f;
  // V-08: the badge over the refused space (350 ms, a transient mark that may cover the field); VS-6 FX-10: sized by
  // the space on screen - clamp(0.3 x its diameter, 24, 32) px (S08FieldFx::RefuseBadgePx), a repeat < 300 ms keeps it
  FVector2D Edge(0.0, 0.0);
  const bool bEdge = ProjectToViewport(BoardModel.CellToWorld(CellX, CellY) + FVector(41.0f, 0.0f, 0.0f), Edge);
  const float BadgePx = S08FieldFx::RefuseBadgePx(bEdge ? 2.0f * static_cast<float>((Edge - Screen).Size()) : 100.0f);
  const bool bShown = UmHud->Feed.ShowBadge(Screen / Px, static_cast<double>(NowMs()), BadgePx / Px);
  FS08Trace::Write(FString::Printf(TEXT("HUD-REFUSE at=cell cell=%s px=%.0f restart=%d"), *BoardModel.CellLabel(CellX, CellY),
                                   BadgePx, bShown ? 1 : 0));
}

void AS08FlowGameMode::UmHudRefusePress(FName PressedId) {
  if (!UmHud.IsValid() || !UmHud->Feed.ToastOnUmg() || !UmHud->bLayout) return;
  const float Px = UmHud->Layout.PxPerSu > 0.0f ? UmHud->Layout.PxPerSu : 1.0f;
  // next to the refused button: its top-right corner (a Slate button of the command panel), else the pointer over the
  // UMG element (+16, -16 su)
  FVector2D Centre(0.0, 0.0);
  FS08ScreenRect Rect;
  const TWeakPtr<SS09HudPress>* Weak = PressedId.IsNone() ? nullptr : HudPressWidgets.Find(PressedId);
  const TSharedPtr<SS09HudPress> Press = Weak ? Weak->Pin() : nullptr;
  if (Press.IsValid() && WidgetViewportRect(StaticCastSharedPtr<SWidget>(Press), Rect) && !Rect.IsEmpty()) {
    Centre = FVector2D(Rect.X1, Rect.Y0) / Px;
  } else {
    APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    float MX = 0.0f, MY = 0.0f;
    if (!PC || !PC->GetMousePosition(MX, MY)) return;
    Centre = FVector2D(MX, MY) / Px + FVector2D(16.0, -16.0);
  }
  UmHud->Feed.ShowBadge(Centre, static_cast<double>(NowMs()));
  FS08Trace::Write(FString::Printf(TEXT("HUD-REFUSE at=press id=%s"), PressedId.IsNone() ? TEXT("-") : *PressedId.ToString()));
}

bool AS08FlowGameMode::UmHudCursorOverFeed(float X, float Y) const {
  if (!UmHud.IsValid() || !UmHud->bLayout) return false;
  const float Px = UmHud->Layout.PxPerSu > 0.0f ? UmHud->Layout.PxPerSu : 1.0f;
  return UmHud->Feed.CoversPoint(FVector2D(X / Px, Y / Px));
}

// ------------------------------------------------------------------------------------------------ VS-4 HB-43 ACTIONS

void AS08FlowGameMode::BuildUmActions() {
  UUmGameHud* Game = UmHudRoot ? UmHudRoot->GetGameHud() : nullptr;
  if (!UmHud.IsValid() || !Game) return;
  FUmHudRuntime& R = *UmHud;
  if (R.Blocks.IsSlate(FName(TEXT("actions")))) {
    ArtHud.PendingTrace.Add(TEXT("HUD-ACTIONS impl=slate reason=-S08SlateHud=actions"));
    return;
  }
  UUmHudActions* W = CreateWidget<UUmHudActions>(GetWorld(), UUmHudActions::WidgetClass());
  if (!W || !Game->SetBlock(EUmGameSlot::Actions, W)) {
    ArtHud.PendingTrace.Add(TEXT("HUD-ACTIONS impl=umg created=0"));
    return;
  }
  R.Actions = W;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  W->SetInput(HudPress, [WeakThis](const FS09HudPressOutcome& Outcome, EUmActionKey Key) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self) return;
    // DE-014 / UI-INP-011: the answer in the frame of the release - the key's command (DE-015), or CUE-004 with the
    // cell's why.* (a disabled cell is Refused by UUmButton itself)
    Self->HandleHudPressOutcome(Outcome, TFunction<FS09Reason()>(), [WeakThis, Key]() {
      if (AS08FlowGameMode* S = WeakThis.Get()) S->PressUmActionKey(static_cast<int32>(Key));
    });
  });
  FString Missing;
  const bool bParts = W->HasAllParts(&Missing);
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-ACTIONS impl=umg created=1 source=%s parts=%d missing=%s"), *W->SourceName(),
                                          bParts ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
}

bool AS08FlowGameMode::UmActionsOnUmg() const { return UmHud.IsValid() && UmHud->Actions.IsValid(); }

bool AS08FlowGameMode::UmKeyHintsNow() {
  const bool bShown = US08UserSettings::KeyHintsNow();
  if (UmHud.IsValid()) {
    FUmHudRuntime& R = *UmHud;
    const FString Mode = US08UserSettings::KeyHintsModeNow();
    if (R.KeyHintsShown != (bShown ? 1 : 0) || R.KeyHintsMode != Mode) {
      R.KeyHintsShown = bShown ? 1 : 0;
      R.KeyHintsMode = Mode;
      const US08UserSettings* Settings = US08UserSettings::Get();
      const FString Line = FString::Printf(TEXT("HUD-KEYHINTS mode=%s shown=%d completedMatches=%d"), *Mode, bShown ? 1 : 0,
                                           Settings ? Settings->CompletedMatches : 0);
      if (FS08Trace::IsOpen()) {
        FS08Trace::Write(Line);
      } else {
        ArtHud.PendingTrace.Add(Line);
      }
    }
  }
  return bShown;
}

void AS08FlowGameMode::RefreshUmActions() {
  if (!UmHud.IsValid() || !UmHud->bLayout) return;
  FUmHudRuntime& R = *UmHud;
  UUmHudActions* W = R.Actions.Get();
  if (!W) return;
  FUmActionsFrame F;
  F.bClassS = R.Layout.bClassS;
  F.PxPerSu = R.Layout.PxPerSu;
  F.RectSu = R.Layout.Rect(EUmHudBlock::Actions);
  F.CanvasSu = R.Layout.CanvasSu;
  F.MarginSu = R.Layout.MarginSu;
  W->SetFrame(F);
  FUmActionsInput In;
  const bool bStarted = Flow.IsValid() && Flow->GetStage() == ES08Stage::Started;
  const bool bAborted = bStarted && Flow->IsRoomAborted();
  In.bShow = bStarted && Hud.bValid && !Hud.bGameOver && !bAborted && !IsResultScreenShown();
  In.bViewerTurn = Hud.bViewerTurn;
  In.ActionsRemaining = Hud.ActionsRemaining;
  In.Mode = CommandUi.Mode;
  if (bStarted) {
    const FS08Snapshot& Snap = EffectiveSnapshot();
    In.bManeuverPending = !FS08Contracts::PendingManeuverId(Snap).IsEmpty();
    In.Busy = HudBusyReason();
    FString Reason;
    FS09Reason Key;
    if (!CommandUi.CanBeginManeuver(Snap, Reason, Key)) In.BeginRefusal = Key;
    In.EndTurn = In.Busy.IsSet() ? In.Busy : CommandUi.EndTurnReason(Snap);
    In.bNoScheme = Hud.bViewerTurn && CommandUi.CountPlayableSchemes(Snap, Fighters) <= 0;
  }
  In.bCombat = CommandUi.Combat.bPresent;
  In.bKeyHints = UmKeyHintsNow();
  W->ApplyModel(UmHudActions::Decide(In));
}

void AS08FlowGameMode::PressUmActionKey(int32 Key) {
  // DE-015: the cell and its key give one answer - the same commands as M / A / G / E in HandleHudKeys
  switch (Key) {
    case 0:
      BeginManeuverCommand();
      return;
    case 1:
      if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
        CancelDraft();  // A toggles the local draft closed
      } else {
        BeginAttackDraft();
      }
      return;
    case 2:
      // ВР-VS4-41 (HB-42 ВР-VS2-HB42-05 delta): the attack draft is local - СХЕМА switches the mode (nothing was sent)
      if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
        CommandUi.Mode = ES09CommandMode::None;
        CommandUi.AttackAttackerId.Reset();
        CommandUi.AttackTargetId.Reset();
        CommandUi.AttackCardId.Reset();
        FS08Trace::Write(TEXT("ATTACK-DRAFT-CANCEL local why=scheme"));
      }
      PlaySchemeCommand();
      return;
    case 3:
      EndTurnCommand();
      return;
    default:
      return;
  }
}

bool AS08FlowGameMode::PressUmEndTurnForFlag() {
  // Run B G-LIVE (DE-014) on the UMG cell: a press and a release through UUmButton's own handlers (-> the arbiter ->
  // HandleHudPressOutcome), at the centre of its painted geometry
  UUmHudActions* W = UmHud.IsValid() ? UmHud->Actions.Get() : nullptr;
  UUmButton* B = W ? W->EndTurn.Get() : nullptr;
  if (!B) return false;
  FGeometry Geometry = B->GetCachedGeometry();
  const bool bPainted = Geometry.GetLocalSize().X > 0.0f && Geometry.GetLocalSize().Y > 0.0f;
  if (!bPainted) Geometry = FGeometry::MakeRoot(FVector2D(86.0, 72.0), FSlateLayoutTransform());
  const FVector2D At = Geometry.LocalToAbsolute(Geometry.GetLocalSize() * 0.5f);
  const FPointerEvent Down(0, At, At, TSet<FKey>{EKeys::LeftMouseButton}, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
  const FPointerEvent Up(0, At, At, TSet<FKey>(), EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
  FS08Trace::Write(FString::Printf(TEXT("INPUT hudpress src=flag id=hud.end.turn impl=umg at=(%.0f,%.0f) geom=%s"), At.X, At.Y,
                                   bPainted ? TEXT("painted") : TEXT("synthetic")));
  B->NativeOnMouseButtonDown(Geometry, Down);
  B->NativeOnMouseButtonUp(Geometry, Up);
  return true;
}

// ------------------------------------------------------------------------------------------------ VS-4 FX-38 zone icons

void AS08FlowGameMode::TickUmZoneBadges() {
  if (!UmHud.IsValid() || !UmHud->Blocks.UmgRoot() || UmHud->Blocks.IsSlate(FName(TEXT("zone")))) return;
  FUmHudRuntime& R = *UmHud;
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor || !BoardActor->IsArtActive()) return;
  if (!R.Zones.IsValid()) {
    UUmZoneBadges* W = CreateWidget<UUmZoneBadges>(GetWorld(), UUmZoneBadges::StaticClass());
    if (!W) return;
    W->AddToViewport(0);  // the board layer: under the UMG HUD root (layer 1)
    R.Zones = W;
    FS08Trace::Write(TEXT("HUD-ZONES created=1 layer=0 rollback=-S08SlateHud=zone"));
  }
  UUmZoneBadges* W = R.Zones.Get();
  FUmZoneBadgeInput In;
  float MX = -1.0f, MY = -1.0f;
  const bool bMouse = PC->GetMousePosition(MX, MY);
  // hidden: no live board, the result, a combat on screen, a modal over the field, the pointer over a HUD block
  const bool bBlocked = !Hud.bValid || IsResultScreenShown() || CommandUi.Combat.bPresent || CombatStage.IsActive() || bInspecting ||
                        DeckPanel.IsOpen() || !bMouse || CursorOverHud();
  if (!bBlocked) {
    // the pick only when the pointer moved or every few frames (a still pointer over a moving camera)
    const FVector2D Mouse(MX, MY);
    if (!Mouse.Equals(R.ZoneMouse, 0.5) || GFrameCounter >= R.ZonePickFrame + FUmBoardCursor::RepickFrames) {
      R.ZoneMouse = Mouse;
      R.ZonePickFrame = GFrameCounter;
      FString FighterId;
      R.ZoneCell = FIntPoint(-1, -1);
      PickBoardUnderCursor(PC, R.ZoneCell, FighterId);
    }
    const FS08Cell* Cell = R.ZoneCell.X >= 0 ? BoardModel.CellAt(R.ZoneCell.X, R.ZoneCell.Y) : nullptr;
    FVector2D Centre;
    const FVector World = Cell ? BoardModel.CellToWorld(R.ZoneCell.X, R.ZoneCell.Y) : FVector::ZeroVector;
    if (Cell && BoardModel.IsBoardSpace(R.ZoneCell.X, R.ZoneCell.Y) && ProjectToViewport(World, Centre)) {
      const float RadiusUU = BoardModel.bHasTopology ? BoardModel.LayoutFrame.SpaceRadiusUU() : 0.5f * FS08BoardModel::CellSizeUU;
      FVector2D Ex, Ey;
      float RadiusPx = 0.0f;
      if (ProjectToViewport(World + FVector(RadiusUU, 0.0f, 0.0f), Ex)) RadiusPx = FMath::Max(RadiusPx, static_cast<float>((Ex - Centre).Size()));
      if (ProjectToViewport(World + FVector(0.0f, RadiusUU, 0.0f), Ey)) RadiusPx = FMath::Max(RadiusPx, static_cast<float>((Ey - Centre).Size()));
      In.bShow = RadiusPx > 0.0f;
      In.SpaceId = Cell->SpaceId.IsEmpty() ? BoardModel.CellLabel(R.ZoneCell.X, R.ZoneCell.Y) : Cell->SpaceId;
      for (const FString& Z : Cell->Zones) In.Keys.Add(FName(*Z.ToLower()));
      In.CentrePx = Centre;
      In.RadiusPx = RadiusPx;
      In.AnchorPx = RadiusUU > 0.0f ? RadiusPx * UmZoneBadges::AnchorUU / RadiusUU : RadiusPx;
      for (const TPair<FString, FS08ScreenRect>& F : FigureScreenRects()) In.Avoid.Add(F.Value);
      for (const FS08ArtHudRuntime::FTagSlot& T : ArtHud.Tags) {
        if (!T.FighterId.IsEmpty() && !T.Planned.IsEmpty()) In.Avoid.Add(T.Planned);
      }
    }
  }
  FVector2D Viewport(1920.0, 1080.0);
  if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(Viewport);
  In.ViewportPx = Viewport;
  In.DiscColor = [this](FName Key, FColor& Out) { return BoardActor && BoardActor->GetZoneIconSrgb(Key, Out); };
  W->SetPxPerUnit(HudPixelsPerUnit());
  const FString Before = W->GetSpaceId();
  W->ApplyInput(In);
  if (W->GetSpaceId() != Before) {
    TArray<FString> Lines;
    W->CollectShotLines(Lines);
    for (const FString& L : Lines) FS08Trace::Write(TEXT("HUD-ZONE ") + L.Mid(5));  // 'HUD-ZONE widget id=zone ...' on a change
  }
}

// ------------------------------------------------------------------------------------------------ VS-4 V4 (H13): INSPECT

void AS08FlowGameMode::BuildUmInspect() {
  if (!UmHud.IsValid() || !UmHudRoot || !UmHudRoot->Modals) return;
  FUmHudRuntime& R = *UmHud;
  if (R.Blocks.IsSlate(FName(TEXT("inspect")))) {
    ArtHud.PendingTrace.Add(TEXT("HUD-INSPECT-UMG impl=slate reason=-S08SlateHud=inspect"));
    return;
  }
  UUmScreenInspect* S = CreateWidget<UUmScreenInspect>(UmHudRoot, UUmScreenInspect::WidgetClass());
  if (!S) {
    ArtHud.PendingTrace.Add(TEXT("HUD-INSPECT-UMG impl=umg created=0 reason=create-failed"));
    return;
  }
  if (UOverlaySlot* O = UmHudRoot->Modals->AddChildToOverlay(S)) {
    O->SetHorizontalAlignment(HAlign_Fill);
    O->SetVerticalAlignment(VAlign_Fill);
  }
  R.Inspect = S;
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  UUmScreenInspect::FInput In;
  In.OnClose = [WeakThis](const TCHAR* Why) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->UmHud.IsValid()) return;
    // read-only: closing clears the inspect state, nothing is sent (UI-INP-006)
    Self->bInspecting = false;
    Self->InspectedHandIndex = -1;
    Self->UmHud->bInspectDeck = false;
    Self->UmHud->InspectKey.Reset();
    FS08Trace::Write(FString::Printf(TEXT("INSPECT close why=%s"), Why));
    Self->RefreshHud();
  };
  In.OnPage = [WeakThis](int32 DeckIndex) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self) return;
    // CRD-INSPECT-PAGE rides on a new inspected id (TickAudio); the deck model stays the grid's
    Self->InspectedCard = FS09CardView();
    Self->InspectedCard.InstanceId = DeckIndex >= 0 ? FString::Printf(TEXT("grid:%d"), DeckIndex) : FString(TEXT("grid"));
    FS08Trace::Write(FString::Printf(TEXT("INSPECT page index=%d"), DeckIndex));
  };
  S->SetInput(HudPress, MoveTemp(In));
  FString Missing;
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-INSPECT-UMG impl=umg created=1 source=%s parts=%d missing=%s"), *S->SourceName(),
                                          S->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
}

bool AS08FlowGameMode::UmInspectOnUmg() const { return UmHud.IsValid() && UmHud->Inspect.IsValid(); }

bool AS08FlowGameMode::UmInspectShown() const { return UmInspectOnUmg() && UmHud->Inspect->IsOpen(); }

FUmInspectContext AS08FlowGameMode::UmInspectContextNow() const {
  FUmInspectContext C;
  C.Own = Hud.ViewerPanel();
  C.Opp = Hud.OpponentPanel();
  if (C.Own) {
    C.OwnHero = PlayerHeroName(C.Own->PlayerId);
    C.OwnSlug = UmDeckHeroSlug(Fighters, C.Own->PlayerId);
  }
  if (C.Opp) {
    C.OppHero = PlayerHeroName(C.Opp->PlayerId);
    C.OppSlug = UmDeckHeroSlug(Fighters, C.Opp->PlayerId);
  }
  C.Lists = &DeckLists;
  return C;
}

void AS08FlowGameMode::NoteUmInspectSource(uint8 Source) {
  if (UmHud.IsValid()) UmHud->InspectSourceNext = static_cast<EUmInspectSource>(Source);
}

void AS08FlowGameMode::OpenUmInspectDeck(bool bOwnSide) {
  // SC-23: «Весь состав» of the deck panel - the grid of that side's deck list (catalogue order, F-05)
  if (!UmInspectOnUmg()) return;
  const FUmInspectModel M = UmInspect::FromDeck(bOwnSide, EUmInspectSource::DeckAll, UmInspectContextNow());
  if (M.Mode != EUmInspectMode::Deck) {
    FS08Trace::Write(TEXT("INSPECT deck refused why=no-list"));
    return;
  }
  UmHud->bInspectDeck = true;
  UmHud->bInspectDeckOwn = bOwnSide;
  UmHud->InspectSourceNext = EUmInspectSource::DeckAll;
  UmHud->InspectKey.Reset();
  InspectedCard = FS09CardView();
  InspectedCard.InstanceId = TEXT("grid");
  InspectedHandIndex = -1;
  bInspecting = true;
  RefreshHud();
}

void AS08FlowGameMode::HandleUmLogInspect(const FString& CardId) {
  // 04 §1.7: a log line opens its card - the catalogue card of whichever deck list has it (public, gameDeckLists)
  for (const FS09DeckList& List : DeckLists) {
    const FS09DeckListCard* C = List.Cards.FindByPredicate([&CardId](const FS09DeckListCard& X) { return X.CardId == CardId; });
    if (!C) continue;
    NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Log));
    InspectCard(UmInspect::DeckCardView(*C));
    InspectedHandIndex = -1;
    DiscardBrowserIndex = -1;
    InspectedSource = 3;
    RefreshHud();
    return;
  }
}

void AS08FlowGameMode::TickUmInspect() {
  if (!UmInspectOnUmg() || !UmHud->bLayout) return;
  TickUmInspectShots();  // VS-4 V4 evidence (opt-in -S08InspectShots)
  FUmHudRuntime& R = *UmHud;
  UUmScreenInspect* S = R.Inspect.Get();
  S->ApplyCanvas(R.Layout.CanvasSu, R.Layout.bClassS, R.Layout.PxPerSu);
  // the live match only (the result screen takes the picture)
  const bool bWant = bInspecting && Hud.bValid && !IsResultScreenShown();
  if (!bWant) {
    if (S->IsOpen()) S->Close(TEXT("owner"));
    R.InspectKey.Reset();
    return;
  }
  const FString Key = R.bInspectDeck ? FString::Printf(TEXT("deck:%d"), R.bInspectDeckOwn ? 1 : 0)
                                     : FString::Printf(TEXT("card:%s|%s|%d"), *InspectedCard.InstanceId, *InspectedCard.CardId,
                                                       InspectedCard.bHidden ? 1 : 0);
  if (S->IsOpen() && Key == R.InspectKey) return;
  const FUmInspectContext Ctx = UmInspectContextNow();
  EUmInspectSource Source = R.InspectSourceNext.IsSet() ? R.InspectSourceNext.GetValue()
                            : InspectedSource == 0      ? EUmInspectSource::Hand
                            : InspectedSource == 3      ? EUmInspectSource::DeckRow
                                                        : EUmInspectSource::Discard;
  R.InspectSourceNext.Reset();
  FUmInspectModel M = R.bInspectDeck ? UmInspect::FromDeck(R.bInspectDeckOwn, Source, Ctx) : UmInspect::FromCard(InspectedCard, Source, Ctx);
  if (R.bInspectDeck && M.Mode != EUmInspectMode::Deck) {
    bInspecting = false;
    R.bInspectDeck = false;
    return;
  }
  R.InspectKey = Key;
  S->Open(M);
  FS08Trace::Write(UmInspect::OpenLine(M));
}

bool AS08FlowGameMode::UmInspectOwnsInput() {
  if (!UmInspectOnUmg() || !Flow.IsValid() || Flow->GetStage() != ES08Stage::Started) return false;
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC) return false;
  UUmScreenInspect* S = UmHud->Inspect.Get();
  if (S->IsOpen()) {
    // 04 §1: the input outside a modal is closed - its keys are the modal's, nothing reaches the board or a command
    for (const FKey& K : {EKeys::Escape, EKeys::I, EKeys::Tab, EKeys::BackSpace}) {
      if (PC->WasInputKeyJustPressed(K)) S->HandleKey(K);
    }
    return true;
  }
  if (IsResultScreenShown() || !Hud.bValid) return false;
  // the slot card (HitTestInvisible: the field click passes through it) - a right click on it opens the inspector
  float MX = 0.0f, MY = 0.0f;
  const UUmHudSourceSlot* Slot = UmHud->Slot.Get();
  if (Slot && PC->WasInputKeyJustPressed(EKeys::RightMouseButton) && PC->GetMousePosition(MX, MY)) {
    const float Px = UmHud->Layout.PxPerSu > 0.0f ? UmHud->Layout.PxPerSu : 1.0f;
    const FBox2D Rect = Slot->CardRectSu();
    if (Rect.bIsValid && Rect.IsInside(FVector2D(MX / Px, MY / Px))) {
      const FUmSlotModel& M = Slot->GetModel();
      FS09CardView Card = M.Card;
      if (!M.bFace) {
        Card = FS09CardView();  // QA-005: a back in the slot opens the hidden card, nothing of its face
        Card.bHidden = true;
        Card.CardId = TEXT("hidden");
      }
      NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Slot));
      InspectCard(Card);
      InspectedHandIndex = -1;
      DiscardBrowserIndex = -1;
      RefreshHud();
      return true;
    }
  }
  // the key I: the selected card of the hand, else the hovered one (04 §1.7); nothing selected - the key does nothing
  if (PC->WasInputKeyJustPressed(EKeys::I)) {
    const FS09PlayerPanel* Own = Hud.ViewerPanel();
    const UUmHudHand* Hand = UmHud->Hand.Get();
    int32 Index = INDEX_NONE;
    if (Hand) {
      const TArray<FUmHandCardModel>& Cards = Hand->GetModel().Cards;
      Index = Cards.IndexOfByPredicate([](const FUmHandCardModel& C) { return C.bSelected; });
      if (Index == INDEX_NONE) Index = Hand->GetHoverIndex();
    }
    if (Own && Own->Cards.IsValidIndex(Index)) {
      NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Key));
      InspectCard(Own->Cards[Index]);
      InspectedHandIndex = Index;
      InspectedSource = 0;
      RefreshHud();
    } else {
      FS08Trace::Write(TEXT("INSPECT key-i nothing-selected"));
    }
    return true;
  }
  return false;
}

void AS08FlowGameMode::UmNoteCardFlashes(const TArray<float>& Flashes, int32 Seq) {
  // VS-4 CP-21 (G-CUE): one CUE-006 show per seq on the game clock; a new play cuts the running one (replace)
  if (!UmHud.IsValid() || Flashes.Num() == 0) return;
  FUmHudRuntime& R = *UmHud;
  if (Seq == R.FlashSeq) return;
  const int64 Now = NowMs();
  if (R.FlashDoneMs >= 0) {
    FS08Trace::Write(UmCardWidget::FlashDoneLine(R.FlashSeq, Now, Now - R.FlashStartMs, TEXT("replace")));
  }
  float Ms = 0.0f;
  for (const float F : Flashes) Ms = FMath::Max(Ms, F);
  R.FlashSeq = Seq;
  R.FlashStartMs = Now;
  R.FlashDoneMs = Now + static_cast<int64>(FMath::RoundToInt(Ms));
  FS08Trace::Write(UmCardWidget::FlashCueLine(Seq, Now, S08IconMotion::IsReducedMotion()));
}

void AS08FlowGameMode::TickUmCardFlashCue() {
  if (!UmHud.IsValid() || UmHud->FlashDoneMs < 0) return;
  FUmHudRuntime& R = *UmHud;
  const int64 Now = NowMs();
  if (Now < R.FlashDoneMs) return;
  FS08Trace::Write(UmCardWidget::FlashDoneLine(R.FlashSeq, Now, Now - R.FlashStartMs));
  R.FlashDoneMs = -1;
}

void AS08FlowGameMode::NoteUmInspectShotsTurn(bool bOwn, bool bInitial, bool bGameOver) {
  if (!UmHud.IsValid() || UmHud->InspectShots != 1 || !bOwn || bInitial || bGameOver || UmHud->InspectTurnAt >= 0.0f) return;
  // the first non-initial own turn: the auto plan waits while the inspector shows its states
  UmHud->InspectTurnAt = Elapsed;
  S09SchemeQuietUntil = FMath::Max(S09SchemeQuietUntil, Elapsed + 7.5f);
  FS08Trace::Write(FString::Printf(TEXT("INSPECTSHOT turn at=%.2f hold=7.5"), Elapsed));
}

void AS08FlowGameMode::TickUmInspectShots() {
  // VS-4 V4 evidence (opt-in -S08InspectShots, with -S08ScreenShots and -S09ShotDir): the H13 states in a live match -
  // the own hand card, the opponent's hidden hand, the own deck grid and a grid card, 1.4 s each from the first
  // non-initial own turn + 1 s (TickUmScreenShots frames UI-SCR-INSPECT-own / -hidden / -deck); HB-47: while the deck
  // lists still load (a slow reply, tools/s10/delay-graphql-query-proxy.cjs) the own deck panel opens and its skeleton
  // is framed 0.8 s later (s09-hb47-skeleton.png)
  FUmHudRuntime& R = *UmHud;
  if (R.InspectShots < 0) {
    R.InspectShots = FParse::Param(FCommandLine::Get(), TEXT("S08InspectShots")) ? 1 : 0;
    // -S08InspectShotsSkeleton=<s>: the skeleton frame not before that long after the first live HUD frame (the board's
    // textures stream in during the first seconds of a match); the panel open >= 0.4 s and its skeleton drawn
    FParse::Value(FCommandLine::Get(), TEXT("S08InspectShotsSkeleton="), R.SkeletonAfter);
    R.SkeletonAfter = FMath::Max(0.3f, R.SkeletonAfter);
  }
  if (R.InspectShots != 1 || !Flow.IsValid() || !Hud.bValid || IsResultScreenShown()) return;
  if (R.SkeletonFirstAt < 0.0f) R.SkeletonFirstAt = Elapsed;
  if (!R.bSkeletonShotDone && UmDeckPanelOnUmg()) {
    const bool bLoading = Flow->GetDeckListsState() != FS08FlowController::EDeckListsState::Loaded;
    if (bLoading && !DeckPanel.IsOpen()) {
      // (again after an auto-close: the turn start closes the panel, 04 §2.9)
      ToggleDeckPanel(ES09DeckSide::Own, TEXT("inspect-shots"));
      R.SkeletonOpenAt = Elapsed;
    } else if (bLoading && R.SkeletonOpenAt >= 0.0f && Elapsed - R.SkeletonOpenAt >= 0.4f && Elapsed - R.SkeletonFirstAt >= R.SkeletonAfter &&
               R.DeckBlocks.GetPanel() && R.DeckBlocks.GetPanel()->IsSkeletonShown() && !UmInspectShown() && !S09ShotDir.IsEmpty()) {
      FS08Trace::Write(FString::Printf(TEXT("INSPECTSHOT skeleton waited=%.2f file=s09-hb47-skeleton.png"), Elapsed - R.SkeletonOpenAt));
      TakeEvidenceShot(S09ShotDir / TEXT("s09-hb47-skeleton.png"));
      R.bSkeletonShotDone = true;
      R.SkeletonDoneAt = Elapsed;
    } else if (!bLoading) {
      R.bSkeletonShotDone = true;  // the lists came first: no skeleton to frame
      FS08Trace::Write(TEXT("INSPECTSHOT skeleton none (lists loaded)"));
    }
  }
  if (R.InspectTurnAt < 0.0f || R.InspectShotStep > 4 || !R.bSkeletonShotDone) return;
  // the inspector states after the skeleton frame (both own the screen)
  const float T = Elapsed - FMath::Max(R.InspectTurnAt, R.SkeletonDoneAt);
  if (T < 1.0f + 1.4f * R.InspectShotStep) return;
  UUmScreenInspect* S = R.Inspect.Get();
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  const int32 Step = R.InspectShotStep++;
  FS08Trace::Write(FString::Printf(TEXT("INSPECTSHOT step=%d t=%.2f"), Step, T));
  if (Step == 0 && Own && Own->Cards.Num() > 0) {
    NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::Hand));
    InspectCard(Own->Cards[0]);
    InspectedHandIndex = 0;
    InspectedSource = 0;
  } else if (Step == 1) {
    FS09CardView Hidden;  // the opponent's hand: the backs only
    Hidden.bHidden = true;
    Hidden.CardId = TEXT("hidden");
    NoteUmInspectSource(static_cast<uint8>(EUmInspectSource::OppHand));
    InspectCard(Hidden);
  } else if (Step == 2) {
    OpenUmInspectDeck(true);
  } else if (Step == 3 && S && S->IsOpen()) {
    S->OpenDeckCard(0);
  } else if (Step == 4 && S) {
    S->Close(TEXT("owner"));
  }
  RefreshHud();
}

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
//       sub/toast the subtitle in a panel.bg capsule, stacked under the toasts over the hand, moving to the top strip
//                when it would cross a figure, its tag or the plate (ВР-H06, 04 §2.12-§2.13) - TickUmHud.
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
#include "S08FlowGameMode.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudStyle.h"
#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08TraceLog.h"
#include "S08TurnPortraitWidget.h"
#include "UI/UmCardGallery.h"
#include "UI/UmCardMedia.h"
#include "UI/UmCombatGallery.h"
#include "UI/UmCursor.h"
#include "UI/UmDecksGallery.h"
#include "UI/UmGameHud.h"
#include "UI/UmHandGallery.h"
#include "UI/UmHudGallery.h"
#include "UI/UmHudBanner.h"
#include "UI/UmHudCombatBlocks.h"
#include "UI/UmScreenBase.h"
#include "UI/UmHudDeckBlocks.h"
#include "UI/UmHudHand.h"
#include "UI/UmHudLayout.h"
#include "UI/UmHudPanels.h"
#include "UI/UmHudPerf.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmHudStatusLine.h"
#include "UI/UmHudTheme.h"
#include "UI/UmHudTop.h"
#include "UI/UmTopStrip.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "DynamicRHI.h"
#include "RenderTimer.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
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
  // the toast / subtitle stack
  bool bSubStyled = false;
  TSharedPtr<SBorder> SubCapsule;  // the capsule the subtitle text moved into (its size is the subtitle's size)
  bool bStackTop = false;
  FBox2D ToastRect = FBox2D(ForceInit);
  FBox2D SubRect = FBox2D(ForceInit);
  float SubYApplied = -1.0f;
  FString LastStackLine;
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
  // VS-3 HUD budget (-S08HudPerf, HUD-RULES П8): -1 not read / 0 off / 1 measuring / 2 finished
  int32 Perf = -1;
  float PerfStartAt = -1.0f;
  bool bPerfShown = true;
  FUmHudPerfMeter PerfMeter;
  double TimerDeadlineSec = 0.0;
  float TimerWindowSec = 30.0f;
  float BannerShiftSu = 0.0f;
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
           "unknown=%s"),
      *R.Source, Game ? (Game->UsesCodeDefaultTree() ? TEXT("code-default") : *Game->GetClass()->GetPathName()) : TEXT("none"),
      bRootParts ? 1 : 0, bGameParts ? 1 : 0,
      (RootMissing + GameMissing).IsEmpty() ? TEXT("-") : *(RootMissing + TEXT(" ") + GameMissing),
      R.Blocks.Blocks.Num() ? *R.Blocks.ImplField() : TEXT("-"), Unknown.Num() ? *FString::Join(Unknown, TEXT(",")) : TEXT("-")));
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
  R.TopStrip.SetFrame(StripFrame);
  const FBox2D OppHandRect = R.Layout.Rect(EUmHudBlock::OppHand);  // VS-2 HB-18...HB-21
  R.Panels.SetFrame(R.Layout.bClassS, R.Layout.PxPerSu,
                    OppHandRect.bIsValid ? static_cast<float>(OppHandRect.Max.X - OppHandRect.Min.X) : 0.0f);
  R.SlateHandLiftSu = R.Layout.HandVisibleSu + 22.0f + 8.0f;  // VS-3 HB-24 (ВР-VS3-22)
  if (UUmHudHand* Hand = R.Hand.Get()) Hand->SetFrame(FUmHandFrame::FromLayout(R.Layout, CombatSpeedMul()));
  RefreshUmDecks();  // VS-3 HB-27 / HB-28: the chips and the panel take the new rects
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
  // the old place: 150 su over the bottom edge (BuildHudWidgets)
  const FMargin Legacy(0.0f, -150.0f, 0.0f, -150.0f);
  if (!UmHud.IsValid() || !UmHud->bLayout || UmHudBlockOnSlate(TEXT("toast")) || !UmHud->ToastRect.bIsValid) return Legacy;
  // anchors (0.5, 1), alignment (0.5, 1): the offset is the bottom centre relative to the canvas bottom centre
  const float Bottom = static_cast<float>(UmHud->ToastRect.Max.Y - UmHud->Layout.CanvasSu.Y);
  return FMargin(0.0f, Bottom, 0.0f, Bottom);
}

void AS08FlowGameMode::UmHudDeckPanelLayering(float DeckAlpha) {
  // VS-3 HB-28 (ВР-VS3-41): the Slate inspector (until H13) opens left of the UMG deck panel while that is drawn
  if (UmHud.IsValid()) {
    FUmHudRuntime& R = *UmHud;
    const UUmHudDeckPanel* Panel = R.DeckBlocks.GetPanel();
    const float Shift = Panel && DeckAlpha > 0.0f && bInspecting ? Panel->PanelRectSu().GetSize().X + 8.0f : 0.0f;
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
    const bool bSideOpen = bDiscardBrowserOpen || bInspecting;
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
  if (bInitial || bGameOver || !UmExitShotsOn()) return;
  FUmHudRuntime& R = *UmHud;
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
    UmHudRoot->TickCursors(HudBusyReason().IsSet(), FPlatformTime::Seconds());
  }
  if (!UmHud.IsValid() || !UmHud->bLayout || !UmHud->Blocks.UmgRoot()) return;
  if (UUmHudHand* Hand = UmHud->Hand.Get()) Hand->StepAnimating();  // VS-3 (ВР-VS3-69): the card tweens of the hand
  TickUmTopStrip();  // VS-2 HB-14...HB-16
  TickUmPanels();    // VS-2 HB-18...HB-21
  RefreshUmCombat();  // VS-3 HB-30...HB-33: the staging's clock moves the edges and the centre
  FUmHudRuntime& R = *UmHud;
  // ВР-VS2-73: the Slate command panel (top left until ACTIONS / CENTER, VS-4) starts 8 su under TOP while TOP is shown
  if (const TSharedPtr<SWidget> Cmd = ArtHud.CommandPanel.Pin()) {
    const UUmHudTop* TopW = R.TopStrip.GetTop();
    const float Shift = (TopW && TopW->IsVisible()) ? static_cast<float>(R.Layout.Rect(EUmHudBlock::Top).Max.Y) + 8.0f : 0.0f;
    if (!FMath::IsNearlyEqual(Shift, R.CommandShiftSu, 0.5f)) {
      R.CommandShiftSu = Shift;
      Cmd->SetRenderTransform(Shift > 0.0f ? TOptional<FSlateRenderTransform>(FSlateRenderTransform(FVector2f(0.0f, Shift)))
                                           : TOptional<FSlateRenderTransform>());
      FS08Trace::Write(FString::Printf(TEXT("HUD-CMD shift=%.0f top=%d"), Shift, Shift > 0.0f ? 1 : 0));
    }
    // ВР-VS2-75: an empty command panel (the opponent's turn without a choice) drew a 20 su navy square at the edge
    const float CmdOpacity = (CommandBox.IsValid() && CommandBox->NumSlots() == 0) ? 0.0f : 1.0f;
    if (!FMath::IsNearlyEqual(Cmd->GetRenderOpacity(), CmdOpacity)) Cmd->SetRenderOpacity(CmdOpacity);
  }
  const float PxPerSu = HudPixelsPerUnit() > 0.0f ? HudPixelsPerUnit() : R.Layout.PxPerSu;
  // ---- the top of the hand actually drawn (the Slate panel, its SD-26 offset included): the stack stays over it ----
  float HandTopSu = -1.0f;
  {
    // VS-3 HB-24 (ВР-VS3-22): with the UMG hand the Slate panel holds only lines - transparent while it has none
    const TSharedPtr<SWidget> HandPanel = ArtHud.HandPanel.Pin();
    const bool bUmHand = UmHandOnUmg();
    if (bUmHand) {
      const FBox2D Caption = R.Layout.Rect(EUmHudBlock::HandCaption);
      if (Caption.bIsValid) HandTopSu = static_cast<float>(Caption.Min.Y);
    }
    const bool bEmpty = bUmHand && HandPanel.IsValid() && HandBox.IsValid() && HandBox->NumSlots() == 0 &&
                        HandPanel->GetDesiredSize().Y <= 21.0f;
    if (bUmHand && HandPanel.IsValid() && !FMath::IsNearlyEqual(HandPanel->GetRenderOpacity(), bEmpty ? 0.0f : 1.0f)) {
      HandPanel->SetRenderOpacity(bEmpty ? 0.0f : 1.0f);
    }
    FS08ScreenRect Panel;
    if (!bEmpty && WidgetViewportRect(HandPanel, Panel) && !Panel.IsEmpty()) {
      HandTopSu = HandTopSu >= 0.0f ? FMath::Min(HandTopSu, Panel.Y0 / PxPerSu) : Panel.Y0 / PxPerSu;
    }
  }
  // ---- the toast / subtitle stack (ВР-H06) ----
  const bool bSub = SubtitleBox.IsValid() && SubtitleText.IsValid() && SubtitleBox->GetVisibility() != EVisibility::Collapsed &&
                    !UmHudBlockOnSlate(TEXT("sub"));
  const TSharedPtr<SBorder> ToastBorder = ToastHudBorder.Pin();
  const bool bToast = ToastBorder.IsValid() && ToastBorder->GetVisibility() != EVisibility::Collapsed &&
                      !UmHudBlockOnSlate(TEXT("toast"));
  if (SubtitleBox.IsValid() && SubtitleText.IsValid() && !UmHudBlockOnSlate(TEXT("sub")) && !R.bSubStyled) {
    // 04 §2.13 / 02 §3.5: no text on the scene without a panel - the line goes into a panel.bg capsule
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    SubtitleBox->SetContent(SAssignNew(R.SubCapsule, SBorder)
                                .BorderImage(Theme.SkinFor(TEXT("capsule"), R.Layout.PxPerSu))
                                .Padding(FMargin(Theme.SpaceSu(TEXT("space.m")), Theme.SpaceSu(TEXT("tag.padding.x"))))
                                .HAlign(HAlign_Center)[SubtitleText.ToSharedRef()]);
    SubtitleText->SetShadowOffset(FVector2D::ZeroVector);
    R.bSubStyled = true;
  }
  if (!bSub && !bToast) return;
  TArray<FBox2D> Avoid;
  for (const TPair<FString, FS08ScreenRect>& F : FigureScreenRects()) Avoid.Add(UmHudPxToSu(F.Value, PxPerSu));
  for (const FS08ArtHudRuntime::FTagSlot& Tag : ArtHud.Tags) {
    if (Tag.bShown && !Tag.Planned.IsEmpty()) Avoid.Add(UmHudPxToSu(Tag.Planned, PxPerSu));
  }
  if (ArtHud.bPlateVisible && !ArtHud.PlatePlanned.IsEmpty()) Avoid.Add(UmHudPxToSu(ArtHud.PlatePlanned, PxPerSu));
  // the capsule, not the box: the box's own padding is the placement
  const FVector2D SubSize = bSub ? (R.SubCapsule.IsValid() ? R.SubCapsule->GetDesiredSize() : SubtitleText->GetDesiredSize())
                                 : FVector2D::ZeroVector;
  const FVector2D ToastSize = bToast ? ToastBorder->GetDesiredSize() : FVector2D::ZeroVector;
  bool bTop = false;
  R.SubRect = R.Layout.StackRect(EUmHudBlock::Sub, ToastSize.X, ToastSize.Y, SubSize.X, SubSize.Y, Avoid, bTop, HandTopSu);
  R.ToastRect = R.Layout.StackRect(EUmHudBlock::Toast, ToastSize.X, ToastSize.Y, SubSize.X, SubSize.Y, Avoid, bTop, HandTopSu);
  R.bStackTop = bTop;
  if (bSub && !FMath::IsNearlyEqual(static_cast<float>(R.SubRect.Min.Y), R.SubYApplied, 0.5f)) {
    // only on a change: the box re-lays out, nothing per frame
    R.SubYApplied = static_cast<float>(R.SubRect.Min.Y);
    SubtitleBox->SetVAlign(VAlign_Top);
    SubtitleBox->SetHAlign(HAlign_Center);
    SubtitleBox->SetPadding(FMargin(0.0f, R.SubYApplied, 0.0f, 0.0f));
  }
  const FString Line = FString::Printf(TEXT("HUD-STACK place=%s sub=%d toast=%d subY=%.0f toastY=%.0f avoid=%d"),
                                       bTop ? TEXT("top") : TEXT("bottom"), bSub ? 1 : 0, bToast ? 1 : 0,
                                       bSub ? R.SubRect.Min.Y : -1.0, bToast ? R.ToastRect.Min.Y : -1.0, Avoid.Num());
  if (Line != R.LastStackLine) {
    R.LastStackLine = Line;
    FS08Trace::Write(Line);
  }
}

void AS08FlowGameMode::WriteUmHudShotLines() {
  if (!UmHud.IsValid()) return;
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
  if (!R.LastStackLine.IsEmpty()) FS08Trace::Write(R.LastStackLine);
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
        if (AS08FlowGameMode* Self = WeakThis.Get()) Self->InspectCard(Hidden);
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
  // ВР-VS2-44: «≡» is Esc without a selection -> PAUSE (SC-24, step H16), «Журнал» the LOG list of class S (H11);
  // until those screens exist the press is answered (CUE-003 in HandleHudPressOutcome) and traced
  FS08Trace::Write(FString::Printf(TEXT("HUD-TOP press=%s target=%s pending=1"), What,
                                   FCString::Strcmp(What, TEXT("menu")) == 0 ? TEXT("UI-SCR-PAUSE") : TEXT("UI-HUD-LOG")));
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
  if (!bSkins && !bButtons && !bTopStrip && !bPanels && !bCards && !bHand && !bDecks && !bCombat) return;
  if (IconGallery) IconGallery->SetVisibility(ESlateVisibility::Collapsed);  // the sheet takes the screen
  // the canvas of the sheet: the applied HUD scale (BeginPlay may run before the first window apply - the sheet is
  // built again on every OnUiScaleChanged, which also covers a window or UI-scale change)
  const int32 PageIndex = FMath::Max(0, Page - 1);
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  auto Build = [WeakThis, bSkins, bTopStrip, bPanels, PanelsPage, PageIndex, Variant, SizePx, bCards, CardsPage, bHand,
                HandBoard, bDecks, DecksBoard, bCombat, bConfirm, CombatBoard]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->GetWorld()) return;
    FVector2D Viewport(1920.0, 1080.0);
    if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(Viewport);
    const FUmHudScaleState& Scale = UmHudScale::Current();
    const float PxPerSu = Scale.Window.X > 0 ? Scale.PxPerSu() : 1.0f;
    if (Self->UmGallery) Self->UmGallery->RemoveFromParent();
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
  // 04 §2.6: the right button opens the inspector on the card (the Slate inspector until H13)
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
  // 04 §2.7: the right button on a combat card opens the inspector (the Slate one until H13)
  C.OnInspect = [WeakThis](const FS09CardView& Card) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self) return;
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
    const FBox2D Panel = Center && UmGameHudSlots::ShownByProperty(Center) ? Center->PanelRectSu() : FBox2D(ForceInit);
    const FBox2D BannerRect = R.Layout.Rect(EUmHudBlock::Banner);
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
  if (UmHudRoot && UmHudRoot->GetGameHud() && R.Blocks.UmgRoot() && Hud.bValid) {
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

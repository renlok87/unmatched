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
#include "S08FlowGameMode.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudStyle.h"
#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08TraceLog.h"
#include "S08TurnPortraitWidget.h"
#include "UI/UmCursor.h"
#include "UI/UmGameHud.h"
#include "UI/UmHudGallery.h"
#include "UI/UmHudLayout.h"
#include "UI/UmHudPanels.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmHudTheme.h"
#include "UI/UmHudTop.h"
#include "UI/UmTopStrip.h"
#include "Brushes/SlateRoundedBoxBrush.h"
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
  RefreshUmHudLayout();
}

void AS08FlowGameMode::HandleUmHudScaleChanged(const FUmHudScaleState& /*State*/) { RefreshUmHudLayout(); }

void AS08FlowGameMode::HandleUmHudEndPlay() {
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
    const float Keep = 1.0f - (bSideOpen ? 1.0f : FMath::Clamp(DeckAlpha, 0.0f, 1.0f));
    for (UWidget* W : {static_cast<UWidget*>(R.Panels.GetOpp()), static_cast<UWidget*>(R.Panels.GetOppHand())}) {
      if (W && !FMath::IsNearlyEqual(W->GetRenderOpacity(), Keep, 1.0e-3f)) W->SetRenderOpacity(Keep);
    }
  }
  // deckpanel: what lies under the open deck panel at the right edge fades out with it (the side counters already
  // do): the right combat edge - a read-only panel never shows a block through it or under its short bottom edge
  if (!CombatEdgeRight.IsValid() || UmHudBlockOnSlate(TEXT("deckpanel"))) return;
  CombatEdgeRight->SetRenderOpacity(1.0f - DeckAlpha);
  const EVisibility Want = DeckAlpha > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Visible;
  if (CombatEdgeRight->GetVisibility() != Want) CombatEdgeRight->SetVisibility(Want);
}

void AS08FlowGameMode::WriteUmHudLateLines() {
  // ВР-VS2-77: inside 'SHOT late begin/end' of the file - the deferred blocks with the geometry painted this frame
  if (!UmHud.IsValid() || UmHud->LateIds.Num() == 0) return;
  FUmHudRuntime& R = *UmHud;
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

void AS08FlowGameMode::NoteUmExitShotsTurn(bool bOwn, bool bInitial, bool bGameOver) {
  if (!UmHud.IsValid() || !bAutoS09 || S09ShotDir.IsEmpty() || bInitial || bGameOver) return;
  FUmHudRuntime& R = *UmHud;
  if (R.ExitShots < 0) R.ExitShots = FParse::Param(FCommandLine::Get(), TEXT("S08ExitShots")) ? 1 : 0;
  float& At = bOwn ? R.ExitOwnAt : R.ExitOppAt;
  if (R.ExitShots == 0 || At >= 0.0f) return;  // only the first turn of each side
  At = Elapsed;
  // the own turn stays at rest past its + 3 s frame (the other client sees the opponent thinking as long)
  if (bOwn) S09SchemeQuietUntil = FMath::Max(S09SchemeQuietUntil, Elapsed + 3.4f);
  FS08Trace::Write(FString::Printf(TEXT("EXITSHOT turn=%s seq=%d at=%.2f hold=%s"), bOwn ? TEXT("own") : TEXT("opp"),
                                   Flow.IsValid() ? Flow->GetAppliedSnapshot().SequenceNumber : -1, Elapsed,
                                   bOwn ? TEXT("3.4") : TEXT("0")));
}

void AS08FlowGameMode::TickUmExitShots() {
  if (!UmHud.IsValid() || UmHud->ExitShots != 1 || S09ShotDir.IsEmpty()) return;
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
    break;
  }
}

void AS08FlowGameMode::TickUmHud() {
  TickUmExitShots();  // VS-2 exit frames (-S08ExitShots)
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
  TickUmTopStrip();  // VS-2 HB-14...HB-16
  TickUmPanels();    // VS-2 HB-18...HB-21
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
    FS08ScreenRect Panel;
    if (WidgetViewportRect(ArtHud.HandPanel.Pin(), Panel) && !Panel.IsEmpty()) HandTopSu = Panel.Y0 / PxPerSu;
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
  if (!bSkins && !bButtons && !bTopStrip && !bPanels) return;
  if (IconGallery) IconGallery->SetVisibility(ESlateVisibility::Collapsed);  // the sheet takes the screen
  // the canvas of the sheet: the applied HUD scale (BeginPlay may run before the first window apply - the sheet is
  // built again on every OnUiScaleChanged, which also covers a window or UI-scale change)
  const int32 PageIndex = FMath::Max(0, Page - 1);
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  auto Build = [WeakThis, bSkins, bTopStrip, bPanels, PanelsPage, PageIndex, Variant, SizePx]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->GetWorld()) return;
    FVector2D Viewport(1920.0, 1080.0);
    if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(Viewport);
    const FUmHudScaleState& Scale = UmHudScale::Current();
    const float PxPerSu = Scale.Window.X > 0 ? Scale.PxPerSu() : 1.0f;
    if (Self->UmGallery) Self->UmGallery->RemoveFromParent();
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

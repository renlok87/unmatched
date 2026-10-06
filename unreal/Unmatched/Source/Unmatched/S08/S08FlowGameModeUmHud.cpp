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
#include "S08FlowGameMode.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08TraceLog.h"
#include "S08TurnPortraitWidget.h"
#include "UI/UmCursor.h"
#include "UI/UmGameHud.h"
#include "UI/UmHudGallery.h"
#include "UI/UmHudLayout.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmHudTheme.h"
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
  // deckpanel: what lies under the open deck panel at the right edge fades out with it (the side counters already
  // do): the right combat edge - a read-only panel never shows a block through it or under its short bottom edge
  if (!CombatEdgeRight.IsValid() || UmHudBlockOnSlate(TEXT("deckpanel"))) return;
  CombatEdgeRight->SetRenderOpacity(1.0f - DeckAlpha);
  const EVisibility Want = DeckAlpha > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Visible;
  if (CombatEdgeRight->GetVisibility() != Want) CombatEdgeRight->SetVisibility(Want);
}

void AS08FlowGameMode::TickUmHud() {
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
  FUmHudRuntime& R = *UmHud;
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

void AS08FlowGameMode::UmGalleryBegin(int32 SizePx) {
  const TCHAR* Cmd = FCommandLine::Get();
  int32 Page = 0;
  const bool bSkins = FParse::Param(Cmd, TEXT("S08IconGallerySkins")) || FParse::Value(Cmd, TEXT("S08IconGallerySkins="), Page);
  int32 Variant = 0;
  const bool bButtons = FParse::Param(Cmd, TEXT("S08IconGalleryButtons")) || FParse::Value(Cmd, TEXT("S08IconGalleryButtons="), Variant);
  if (!bSkins && !bButtons) return;
  if (IconGallery) IconGallery->SetVisibility(ESlateVisibility::Collapsed);  // the sheet takes the screen
  // the canvas of the sheet: the applied HUD scale (BeginPlay may run before the first window apply - the sheet is
  // built again on every OnUiScaleChanged, which also covers a window or UI-scale change)
  const int32 PageIndex = FMath::Max(0, Page - 1);
  TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  auto Build = [WeakThis, bSkins, PageIndex, Variant, SizePx]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->GetWorld()) return;
    FVector2D Viewport(1920.0, 1080.0);
    if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(Viewport);
    const FUmHudScaleState& Scale = UmHudScale::Current();
    const float PxPerSu = Scale.Window.X > 0 ? Scale.PxPerSu() : 1.0f;
    if (Self->UmGallery) Self->UmGallery->RemoveFromParent();
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

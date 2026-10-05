// MS-T-17: the opponent view of the game mode (docs/game-design/move-selection 03 §7, S09/S09OpponentView.h) - the
// planning indicator by the opponent's panel line, the last-move highlight V-14 / V-15 on the plates (MS-P-03), the
// event feed over the hand and the edge arrow for an end of the opponent's path outside the viewport (MS-E-73; the
// camera never moves for it, MS-R-31).
#include "S08FlowGameMode.h"

#include "S08BoardActor.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "S08WhyText.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace {
/** Viewport pixels between the screen edge and the edge arrow's centre. */
constexpr float GEdgeArrowMarginPx = 48.0f;
}  // namespace

void AS08FlowGameMode::FeedOpponentView(const FS08Snapshot& Snapshot) {
  const FString ViewerId = bBench ? BenchViewerId : (Flow.IsValid() ? Flow->GetUserId() : FString());
  // MS-S-11: the indicator follows pendingManeuver.playerId; the opponent's draft itself never reaches this client
  const bool bPlanning = S09OpponentView::OpponentPlanning(Snapshot, ViewerId);
  if (!bOpponentPlanningKnown || bPlanning != bOpponentPlanning) {
    if (bOpponentPlanningKnown || bPlanning) {
      FS08Trace::Write(FString::Printf(TEXT("MS-OPP planning=%d seq=%d"), bPlanning ? 1 : 0, Snapshot.SequenceNumber));
    }
    bOpponentPlanning = bPlanning;
    bOpponentPlanningKnown = true;
  }
  TArray<FS08BoardFighter> Decoded;
  if (!FS08BoardModel::DecodeFighters(Snapshot.Fighters, Decoded)) return;
  FS09LastMovement Trail;
  FS09LastMovement::Read(Snapshot.Metadata, Trail);
  const TArray<FString> Lines =
      LastMoveTracker.OnApplied(Snapshot.SequenceNumber, Trail, FS09BoardStamp::Make(Decoded, Snapshot.CurrentTurnPlayerId),
                                static_cast<double>(NowMs()), MoveMotion.bReducedMotion);
  for (const FString& Line : Lines) FS08Trace::Write(Line);
}

void AS08FlowGameMode::TickOpponentView() {
  const double Now = static_cast<double>(NowMs());
  const bool bMoving = BoardActor && BoardActor->AnyFighterMoving();
  for (const FString& Line : LastMoveTracker.Tick(Now, bMoving)) FS08Trace::Write(Line);
  if (BoardActor) BoardActor->SetLastMoveFade(LastMoveTracker.IsDrawn() ? LastMoveTracker.Alpha(Now) : 1.0f);

  // the feed line of a maneuver comes with its highlight (03 §7 "После": MS-P-03 + the line)
  FS09LastMovement Revealed;
  if (LastMoveTracker.ConsumeRevealed(Revealed)) {
    const FString ViewerId = bBench ? BenchViewerId : (Flow.IsValid() ? Flow->GetUserId() : FString());
    auto PlayerName = [this, &ViewerId](const FString& PlayerId) -> FString {
      for (const FS08BoardFighter& F : Fighters) {
        if (F.OwnerId == PlayerId && F.bIsHero) return F.Label.IsEmpty() ? F.Name : F.Label;
      }
      return PlayerId == ViewerId ? FString(TEXT("You")) : FString(TEXT("Opponent"));
    };
    auto FighterName = [this](const FString& FighterId) -> FString {
      const FS08BoardFighter* F = FindFighter(FighterId);
      return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : FighterId;
    };
    auto CellName = [this](const FIntPoint& Cell) { return BoardModel.CellLabel(Cell.X, Cell.Y); };
    if (EventFeed.Add(Revealed, PlayerName, FighterName, CellName)) {
      const FS09FeedEntry& Entry = EventFeed.GetLines().Last();
      FS08Trace::Write(FString::Printf(TEXT("MS-LOG seq=%d moves=%d truncated=%d text=\"%s\""), Entry.Seq, Entry.Moves,
                                       Entry.bTruncated ? 1 : 0, *Entry.Text));
      RefreshHud();
    }
  }

  // MS-E-73: the opponent's path ends outside the viewport -> an arrow at the screen edge (the camera stays)
  S09OpponentView::FEdgeArrow Arrow;
  FString ArrowCell;
  const FS09LastMovement& Trail = LastMoveTracker.GetTrail();
  const FString ViewerId = bBench ? BenchViewerId : (Flow.IsValid() ? Flow->GetUserId() : FString());
  if (LastMoveTracker.GetState() != ES09LastMoveState::None && !ViewerId.IsEmpty() && Trail.PlayerId != ViewerId &&
      GEngine && GEngine->GameViewport) {
    FVector2D Viewport(0.0, 0.0);
    GEngine->GameViewport->GetViewportSize(Viewport);
    for (const FS09LastMovement::FMove& Move : Trail.Moves) {
      const FIntPoint Dest = Move.Dest();
      FVector2D Screen(0.0, 0.0);
      const bool bProjected = ProjectToViewport(BoardModel.CellToWorld(Dest.X, Dest.Y), Screen);
      Arrow = S09OpponentView::EdgeArrow(Screen, bProjected, Viewport, GEdgeArrowMarginPx);
      if (Arrow.bShow) {
        ArrowCell = BoardModel.CellLabel(Dest.X, Dest.Y);
        break;
      }
    }
  }
  EdgeArrowNow = Arrow;
  const FString Key = Arrow.bShow ? FString::Printf(TEXT("1|%s"), *ArrowCell) : FString(TEXT("0"));
  if (Key != EdgeArrowTraceKey) {
    if (!(EdgeArrowTraceKey.IsEmpty() && !Arrow.bShow)) {
      FS08Trace::Write(FString::Printf(TEXT("MS-OPP arrow=%d cell=%s x=%.0f y=%.0f angle=%.0f seq=%d"), Arrow.bShow ? 1 : 0,
                                       Arrow.bShow ? *ArrowCell : TEXT("-"), Arrow.Pos.X, Arrow.Pos.Y, Arrow.AngleDeg,
                                       Trail.Seq));
    }
    EdgeArrowTraceKey = Key;
  }
  if (EdgeArrowGlyph.IsValid()) {
    const float Ppu = HudPixelsPerUnit();
    const bool bShow = Arrow.bShow && Ppu > 0.0f;
    EdgeArrowGlyph->SetVisibility(bShow ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
    if (bShow) {
      if (EdgeArrowSlot) EdgeArrowSlot->SetOffset(FMargin(Arrow.Pos.X / Ppu, Arrow.Pos.Y / Ppu, 0.0f, 0.0f));
      EdgeArrowGlyph->SetRenderTransform(FSlateRenderTransform(FQuat2D(FMath::DegreesToRadians(Arrow.AngleDeg))));
    }
  }
}

FS08MoveDraftInput::FLastMove AS08FlowGameMode::LastMovePlateInput() const {
  if (!LastMoveTracker.IsDrawn()) return FS08MoveDraftInput::FLastMove();
  const FS09LastMovement& Trail = LastMoveTracker.GetTrail();
  // V-14 / V-15 take the mover's team colour as the board draws that team (absolute or -S08TeamColorMode relative)
  const FString ViewerId = bBench ? BenchViewerId : (Flow.IsValid() ? Flow->GetUserId() : FString());
  ES08PlateColor Color = ES08PlateColor::TeamP1;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    const FS08BoardFighter* F = FindFighter(Move.FighterId);
    if (!F || !BoardActor) continue;
    const ES08TeamSlot Look =
        S08TeamLook(BoardActor->TeamOfFighter(*F), F->OwnerId == ViewerId, BoardActor->GetTeamColorMode());
    Color = Look == ES08TeamSlot::P1 ? ES08PlateColor::TeamP1 : ES08PlateColor::TeamP2;
    break;
  }
  return S09OpponentView::LastMoveInput(Trail, Color);
}

void AS08FlowGameMode::BuildOpponentHudWidgets(const TSharedRef<SConstraintCanvas>& Canvas) {
  Canvas->AddSlot()
      .Anchors(FAnchors(0.0f, 0.0f))
      .Alignment(FVector2D(0.5f, 0.5f))
      .AutoSize(true)
      .Offset(FMargin(0.0f, 0.0f, 0.0f, 0.0f))
      .Expose(EdgeArrowSlot)
          [SAssignNew(EdgeArrowGlyph, STextBlock)
               .Text(FText::FromString(TEXT("→")))
               .Font(FCoreStyle::GetDefaultFontStyle("Bold", 44))
               .ColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.86f, 0.55f, 0.95f)))
               .ShadowOffset(FVector2D(1.5f, 1.5f))
               .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f))
               .RenderTransformPivot(FVector2D(0.5f, 0.5f))
               .Visibility(EVisibility::Collapsed)];
}

void AS08FlowGameMode::AddOpponentPanelLines() {
  if (!PanelsBox.IsValid() || !bOpponentPlanning) return;
  // 03 §6: a 1 Hz pulse, none with reduced motion (the indicator is our online decision, DE has none - §7 p. 1)
  PanelsBox->AddSlot().AutoHeight().Padding(0, 2, 0, 2)
      [SNew(STextBlock)
           .Text(FText::FromString(S08WhyText::En(FName(TEXT("ms.opp.planning")))))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
           .ColorAndOpacity_Lambda([this]() {
             const float Alpha = S09OpponentView::PlanningPulse(Elapsed, MoveMotion.bReducedMotion);
             return FSlateColor(FLinearColor(1.0f, 0.86f, 0.55f, Alpha));
           })];
}

void AS08FlowGameMode::AddEventFeedLines() {
  if (!HandBox.IsValid()) return;
  for (const FS09FeedEntry& Entry : EventFeed.GetLines()) {
    // MS-E-106: at most two visual lines at 150 % - the line is cut to two moves + "and N more" and wraps; the full
    // list is the tooltip
    HandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
        [SNew(STextBlock)
             .Text(FText::FromString(Entry.Text))
             .ToolTipText(Entry.bTruncated ? FText::FromString(Entry.Full) : FText::GetEmpty())
             .AutoWrapText(true)
             .WrapTextAt(760.0f)
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 13))
             .ColorAndOpacity(FSlateColor(FLinearColor(0.82f, 0.84f, 0.88f, 1.0f)))];
  }
}

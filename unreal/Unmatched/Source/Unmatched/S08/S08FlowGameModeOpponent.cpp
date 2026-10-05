// MS-T-17: the opponent view of the game mode (docs/game-design/move-selection 03 §7, S09/S09OpponentView.h) - the
// planning indicator by the opponent's panel line, the last-move highlight V-14 / V-15 on the plates (MS-P-03), the
// event feed over the hand and the edge arrow for an end of the opponent's path outside the viewport (MS-E-73; the
// camera never moves for it, MS-R-31).
// DE-022 (W-13; 03 §7 п. 1-3, MS-R-77; 01 F-12; 02-ux-ui-spec SD-31): the opponent's phase verb from the server state
// in place of the planning line, the action tracker rows of both sides (the opponent's only in their turn, 150 ms in),
// the callout "Your fighter X: Y effect" while an opponent's effect moves my fighter along the trail, the effect lines
// of the feed and the "what to do now" line over the hand. The camera stays (MS-R-31): nothing here moves it.
#include "S08FlowGameMode.h"

#include "S08BoardActor.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "S08WhyText.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace {
/** Viewport pixels between the screen edge and the edge arrow's centre. */
constexpr float GEdgeArrowMarginPx = 48.0f;
/** DE-022: the callout of the opponent's effect on my fighter stays at least this long (the read time of MS-R-78's
 *  BOOSTED card, 03 §7 п. 5) and to the end of the move animation; the feed line keeps it afterwards. */
constexpr double GYoursCalloutMinMs = 1000.0;
/** The tracker blocks: the v3 accent gold, a spent slot at opacity 0.4 (01 F-12: v3 "spend = opacity 0.4"). */
const FLinearColor GTrackerSlot(1.0f, 0.86f, 0.55f, 1.0f);
constexpr float GTrackerSpentAlpha = 0.4f;

int32 ActionsRemainingOf(const FS08Snapshot& Snapshot) {
  const TSharedPtr<FJsonObject> Meta =
      Snapshot.Metadata.IsValid() && Snapshot.Metadata->Type == EJson::Object ? Snapshot.Metadata->AsObject() : nullptr;
  if (!Meta.IsValid()) return -1;
  int32 Actions = -1;
  bool bPresent = false;
  return FS08Contracts::ReadIntLike(Meta.ToSharedRef(), TEXT("actionsRemaining"), Actions, bPresent) && bPresent ? Actions
                                                                                                                : -1;
}
}  // namespace

FString AS08FlowGameMode::ViewerIdNow() const {
  return bBench ? BenchViewerId : (Flow.IsValid() ? Flow->GetUserId() : FString());
}

FString AS08FlowGameMode::PlayerHeroName(const FString& PlayerId) const {
  for (const FS08BoardFighter& F : Fighters) {
    if (F.OwnerId == PlayerId && F.bIsHero) return F.Label.IsEmpty() ? F.Name : F.Label;
  }
  return PlayerId == ViewerIdNow() ? FString(TEXT("You")) : FString(TEXT("Opponent"));
}

void AS08FlowGameMode::FeedOpponentView(const FS08Snapshot& Snapshot) {
  const FString ViewerId = ViewerIdNow();
  const double Now = static_cast<double>(NowMs());
  // DE-022 (03 §7 п. 1): what the opponent does now, from the server state
  const ES09OpponentVerb Verb = S09OpponentView::OpponentVerb(Snapshot, ViewerId);
  if (!bOpponentVerbKnown || Verb != OpponentVerbNow) {
    if (bOpponentVerbKnown || Verb != ES09OpponentVerb::None) {
      FS08Trace::Write(FString::Printf(TEXT("MS-OPP verb=%s seq=%d"), S09OpponentView::VerbName(Verb), Snapshot.SequenceNumber));
    }
    OpponentVerbNow = Verb;
    bOpponentVerbKnown = true;
  }
  // DE-022 (01 F-12): the tracker marks by actionsRemaining of the snapshot
  const FString TrackLine = ActionTracker.OnApplied(Snapshot.SequenceNumber, Snapshot.CurrentTurnPlayerId,
                                                    Snapshot.TurnCount, ActionsRemainingOf(Snapshot), ViewerId, Now);
  if (!TrackLine.IsEmpty()) FS08Trace::Write(TrackLine);
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
                                Now, MoveMotion.bReducedMotion);
  for (const FString& Line : Lines) FS08Trace::Write(Line);

  // DE-022 (03 §7 п. 3): an EFFECT trail of this seq - its source card from public data (the resolved choice's text
  // in the mover's discard pile) and my fighters an opponent's effect moved (the callout while the move plays)
  if (Trail.bValid && Trail.Seq == Snapshot.SequenceNumber && Trail.Source == TEXT("EFFECT") &&
      Trail.Seq != EffectTrailSeq) {
    TArray<FS09CardView> MoverDiscard;
    for (const FS09PlayerPanel& Panel : Hud.Panels) {
      if (Panel.PlayerId == Trail.PlayerId) MoverDiscard = Panel.Discard;
    }
    EffectTrailSeq = Trail.Seq;
    EffectTrailCard = S09OpponentView::EffectCardName(EffectSources.TextOf(Trail.SourceRef), MoverDiscard);
    EffectTrailYours = S09OpponentView::YourFightersMoved(Trail, ViewerId, [&Decoded](const FString& Id) {
      const FS08BoardFighter* F = Decoded.FindByPredicate([&Id](const FS08BoardFighter& E) { return E.Id == Id; });
      return F ? F->OwnerId : FString();
    });
    if (EffectTrailYours.Num() > 0) {
      auto FighterName = [&Decoded](const FString& Id) -> FString {
        const FS08BoardFighter* F = Decoded.FindByPredicate([&Id](const FS08BoardFighter& E) { return E.Id == Id; });
        return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : Id;
      };
      const FS09FeedEntry Entry = FS09EventFeed::DescribeEffect(
          Trail, EffectTrailCard, EffectTrailYours, [this](const FString& Id) { return PlayerHeroName(Id); }, FighterName,
          [this](const FIntPoint& Cell) { return BoardModel.CellLabel(Cell.X, Cell.Y); });
      bYoursCallout = true;
      YoursCalloutText = Entry.Text;
      YoursCalloutSinceMs = Now;
      FS08Trace::Write(FString::Printf(TEXT("MS-OPP yours seq=%d fighters=%s card=\"%s\" text=\"%s\""), Trail.Seq,
                                       *FString::Join(EffectTrailYours, TEXT(",")),
                                       EffectTrailCard.IsEmpty() ? TEXT("?") : *EffectTrailCard, *YoursCalloutText));
    }
  }
  EffectSources.Note(S09OpponentView::PendingQueue(Snapshot));
}

void AS08FlowGameMode::TickOpponentView() {
  const double Now = static_cast<double>(NowMs());
  const bool bMoving = BoardActor && BoardActor->AnyFighterMoving();
  for (const FString& Line : LastMoveTracker.Tick(Now, bMoving)) FS08Trace::Write(Line);
  if (BoardActor) BoardActor->SetLastMoveFade(LastMoveTracker.IsDrawn() ? LastMoveTracker.Alpha(Now) : 1.0f);

  // the feed line of a maneuver comes with its highlight (03 §7 "После": MS-P-03 + the line); DE-022: an EFFECT
  // trail writes its effect line (or "Your fighter X: Y effect") the same way
  FS09LastMovement Revealed;
  if (LastMoveTracker.ConsumeRevealed(Revealed)) {
    auto PlayerName = [this](const FString& PlayerId) { return PlayerHeroName(PlayerId); };
    auto FighterName = [this](const FString& FighterId) -> FString {
      const FS08BoardFighter* F = FindFighter(FighterId);
      return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : FighterId;
    };
    auto CellName = [this](const FIntPoint& Cell) { return BoardModel.CellLabel(Cell.X, Cell.Y); };
    const bool bEffect = Revealed.Source == TEXT("EFFECT");
    const bool bSameTrail = Revealed.Seq == EffectTrailSeq;
    const bool bAdded =
        bEffect ? EventFeed.AddEffect(Revealed, bSameTrail ? EffectTrailCard : FString(),
                                      bSameTrail ? EffectTrailYours : TArray<FString>(), PlayerName, FighterName, CellName)
                : EventFeed.Add(Revealed, PlayerName, FighterName, CellName);
    if (bAdded) {
      const FS09FeedEntry& Entry = EventFeed.GetLines().Last();
      FS08Trace::Write(FString::Printf(TEXT("MS-LOG seq=%d moves=%d truncated=%d text=\"%s\""), Entry.Seq, Entry.Moves,
                                       Entry.bTruncated ? 1 : 0, *Entry.Text));
      RefreshHud();
    }
    // Run D G-LIVE (MS-AT-30): the highlight + feed frame of the opponent move whose flight frame was scheduled
    if (bAutoS09 && !S09ShotDir.IsEmpty() && ShotOppMoveAtElapsed >= 0.0f && ShotOppLastAtElapsed < 0.0f &&
        !Revealed.PlayerId.IsEmpty() && Revealed.PlayerId != ViewerIdNow()) {
      ShotOppLastAtElapsed = Elapsed + 0.5f;
      FS08Trace::Write(FString::Printf(TEXT("S09AUTO opponent-last-move shot scheduled seq=%d"), Revealed.Seq));
    }
  }
  // the callout ends once its move played out (the highlight is up) and the minimum read time passed
  if (bYoursCallout && LastMoveTracker.GetState() != ES09LastMoveState::Waiting &&
      Now - YoursCalloutSinceMs >= GYoursCalloutMinMs) {
    bYoursCallout = false;
    FS08Trace::Write(FString::Printf(TEXT("MS-OPP yours off seq=%d ms=%d"), EffectTrailSeq,
                                     FMath::RoundToInt(Now - YoursCalloutSinceMs)));
    RefreshHud();
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
  if (!PanelsBox.IsValid()) return;
  AddActionTrackerRow(true);  // DE-022 (01 F-12): only in the opponent's turn
  // DE-022 (03 §7 п. 1): the verb from the server state - "Opponent is planning a maneuver" (MS-S-11) is one of them
  const FName Key = S09OpponentView::VerbKey(OpponentVerbNow);
  if (Key.IsNone()) return;
  // 03 §6: a 1 Hz pulse, none with reduced motion (the indicator is our online decision, DE has none - §7 p. 1)
  PanelsBox->AddSlot().AutoHeight().Padding(0, 2, 0, 2)
      [SNew(STextBlock)
           .Text(FText::FromString(S08WhyText::En(Key)))
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

void AS08FlowGameMode::AddActionTrackerRow(bool bOpponent) {
  if (!PanelsBox.IsValid()) return;
  // 01 F-12: own always; the opponent's only in their turn, appearing over 150 ms (hidden in the rebuild that applies
  // the turn change - one frame)
  if (bOpponent && !ActionTracker.OpponentVisible()) return;
  const FS09ActionTracker::FSlots Slots = bOpponent ? ActionTracker.Opponent() : ActionTracker.Own();
  TSharedRef<SHorizontalBox> Row = SNew(SHorizontalBox);
  Row->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 6, 0)
      [SNew(STextBlock)
           .Text(FText::FromString(bOpponent ? TEXT("opponent actions") : TEXT("your actions")))
           .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
           .ColorAndOpacity(FSlateColor(FLinearColor(0.82f, 0.84f, 0.88f, 1.0f)))];
  for (int32 Index = 0; Index < Slots.Slots; ++Index) {
    FLinearColor Color = GTrackerSlot;
    if (Index < Slots.Spent) Color.A = GTrackerSpentAlpha;
    Row->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(2, 0)
        [SNew(SBox).WidthOverride(16.0f).HeightOverride(16.0f)[SNew(SColorBlock).Color(Color)]];
  }
  PanelsBox->AddSlot().AutoHeight().Padding(0, 2, 0, 2)
      [SNew(SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
           .Padding(0.0f)
           .ColorAndOpacity_Lambda([this, bOpponent]() {
             const float Alpha =
                 bOpponent ? ActionTracker.OpponentAlpha(static_cast<double>(NowMs()), MoveMotion.bReducedMotion) : 1.0f;
             return FLinearColor(1.0f, 1.0f, 1.0f, Alpha);
           })[Row]];
}

void AS08FlowGameMode::AddYoursCalloutLine() {
  if (!HandBox.IsValid() || !bYoursCallout || YoursCalloutText.IsEmpty()) return;
  // 03 §7 п. 3: the source card and "your fighter" while the opponent's effect moves it along the trail
  HandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 4)
      [SNew(STextBlock)
           .Text(FText::FromString(YoursCalloutText))
           .AutoWrapText(true)
           .WrapTextAt(760.0f)
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 15))
           .ColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.7f, 0.4f, 1.0f)))
           .ShadowOffset(FVector2D(1.0f, 1.0f))
           .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f))];
}

FS09TurnStatusInput AS08FlowGameMode::BuildTurnStatusInput() const {
  FS09TurnStatusInput In;
  const FString ViewerId = ViewerIdNow();
  auto Label = [this](const FString& Id) -> FString {
    if (Id.IsEmpty()) return FString();
    const FS08BoardFighter* F = FindFighter(Id);
    return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : Id;
  };
  In.bGameOver = Hud.bGameOver;
  In.bSyncing = HudBusyReason().IsSet() ||
                (Flow.IsValid() && (Flow->IsAwaitingStateRecovery() ||
                                    (Flow->GetStage() == ES08Stage::Started && !Flow->IsStreamReady())));
  In.bViewerTurn = Hud.bViewerTurn;
  In.ActionsRemaining = Hud.ActionsRemaining;
  In.Mode = CommandUi.Mode;
  switch (CommandUi.Mode) {
    case ES09CommandMode::ManeuverDraft:
      In.SelectedFighterName = Label(CommandUi.SelectedFighterId);
      break;
    case ES09CommandMode::AttackDraft:
      In.bAbilityPrompt = CommandUi.IsAttackAbilityPromptOpen();
      In.AttackerName = Label(CommandUi.AttackAttackerId);
      In.TargetName = Label(CommandUi.AttackTargetId);
      In.bAttackCard = !CommandUi.AttackCardId.IsEmpty();
      break;
    case ES09CommandMode::DiscardDraft:
      In.DiscardNeed = CommandUi.PendingDiscard.Count;
      In.DiscardChosen = CommandUi.DiscardSelection.Num();
      break;
    case ES09CommandMode::PendingChoice: {
      // the prompt the panel shows: the step "object -> target (up to N)", else the MOVE / PLACE prompt, else the
      // choice named by its card text
      const FS09PendingStep Step = S09DescribePendingStep(CommandUi, EffectiveSnapshot(), BoardModel, Fighters);
      const FS09PendingMovePrompt Move = CommandUi.DescribePendingMovePlace(BoardModel, Fighters);
      const FS08PendingEffect& Pending = CommandUi.PendingChoice;
      if (Step.bValid && Step.Prompt.IsSet()) {
        In.PendingPrompt = Step.Prompt;
      } else if (Move.bValid && Move.Prompt.IsSet()) {
        In.PendingPrompt = Move.Prompt;
      } else {
        In.PendingPrompt = FS09Reason::Make(TEXT("ms.status.choice"))
                               .Arg(TEXT("choice"), Pending.Text.IsEmpty() ? Pending.Type : Pending.Text.Left(80));
      }
      break;
    }
    default:
      break;
  }
  In.bOpponentChoice = CommandUi.PendingQueue.Num() > 0 && !CommandUi.PendingQueue[0].PlayerId.IsEmpty() &&
                       CommandUi.PendingQueue[0].PlayerId != ViewerId;
  In.bCombatAttacking = CommandUi.Combat.bPresent && Hud.Phase == TEXT("COMBAT") && !ViewerId.IsEmpty() &&
                        CommandUi.Combat.DefenderId != ViewerId;
  In.OpponentVerb = OpponentVerbNow;
  if (const FS09PlayerPanel* Opponent = Hud.OpponentPanel()) In.OpponentName = PlayerHeroName(Opponent->PlayerId);
  return In;
}

void AS08FlowGameMode::AddTurnStatusLine() {
  if (!HandBox.IsValid()) return;
  // 02-ux-ui-spec SD-31: one line "what to do now" in every state; it does not empty while a figure moves (CUE-007
  // blocks_input: no)
  const FString Text = S09TurnStatus::Text(BuildTurnStatusInput());
  if (Text != TurnStatusTraceKey) {
    FS08Trace::Write(FString::Printf(TEXT("MS-STATUS seq=%d text=\"%s\""), Hud.SequenceNumber, *Text));
    TurnStatusTraceKey = Text;
  }
  if (Text.IsEmpty()) return;
  HandBox->AddSlot().AutoHeight().Padding(0, 2, 0, 6)
      [SNew(STextBlock)
           .Text(FText::FromString(Text))
           .AutoWrapText(true)
           .WrapTextAt(760.0f)
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
           .ColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.95f, 0.8f, 1.0f)))
           .ShadowOffset(FVector2D(1.0f, 1.0f))
           .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f))];
}

// DE-023 (W-15 HUD; 01 F-07, F-12, D-DE-07, D-DE-12, review resolution pp. 6, 9; 02 SD-08, SD-25, SD-34, SD-35;
// 02-ux-ui-spec §4.3 "Ход и действия"; ICON-MOTION.md "Трекер действий: поведение игры"): the turn HUD of the game mode.
//   - Two persistent UMG portraits (US08TurnPortraitWidget) in the left column at the bottom - the opponent above,
//     mine below (02 §4.1: UI-HUD-PANEL-OPP over UI-HUD-PANEL-LOC; the top-left corner is the S09 command panel).
//     They are built once with the HUD and never recreated by RefreshHud: the ring, the tracker marks and the heart
//     pulse play on them (02 §4.3 п. 4).
//   - The turn ring at BOTH sides on the active player's portrait (FS09TurnCue): appear = the flash 1000 ms, then the
//     smouldering rim to the end of the turn; reduced motion = a static rim. Drawn only with -S08TurnRingIcon=<id>
//     until the user's art acceptance of the DE-012 ring glyph (IMPL: candidates are prepared, not on by default).
//   - The "Your turn" banner (CUE-015): own turn only, 600 ms (reduced 100), hit-test invisible - input stays open
//     from the apply (DE-015).
//   - The trackers: mine marks the slot at the choice (FS09TrackerMarks - a local attack / scheme draft or the sent
//     command) and gives it back on cancel; the opponent's shows only in their turn, fading in over 150 ms
//     (FS09ActionTracker, DE-022). A new turn snaps both in one frame.
//   - The hero heart: damage / deplete / heal when the SHOWN hero HP changes (HudFighters: the combat staging holds the
//     HP to the contact + 80 ms); damage plays without the `glow` candidate layer unless -S08HeartGlow.
// Off the art look (-S08GreyBoard, the S09 HUD harness) nothing is built and the DE-022 Slate tracker rows stay.
// Trace: 'HUD-TURN config ...', 'HUD-TURN seq=... turn=own|opp ...', 'HUD-TRACK ...', 'HUD-HEART ...'.
#include "S08FlowGameMode.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudStyle.h"
#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "S08TurnPortraitWidget.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace {
/** Left / bottom gap of the portrait column and the gap between the two portraits (slate units). */
constexpr float GPortraitEdgeSu = 24.0f;
constexpr float GPortraitGapSu = 8.0f;
/** The banner sits under the combat outcome slot (top centre, +24) - no combat is open at a turn start. */
constexpr float GBannerTopSu = 132.0f;

FLinearColor BannerSrgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}
}  // namespace

void AS08FlowGameMode::BuildTurnHudWidgets(const TSharedRef<SConstraintCanvas>& Canvas) {
  // BuildUi runs before the trace opens: the lines wait in ArtHud.PendingTrace like the other HUD config lines.
  UWorld* World = GetWorld();
  if (!S08ArtLook::Enabled() || !World) {
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-TURN config portraits=0 reason=%s"),
                                            World ? TEXT("grey-board") : TEXT("no-world")));
    return;
  }
  TurnHudLook = FS08TurnHudLook::FromCommandLine(FCommandLine::Get());
  const FS08ArtHudPlateStyle Chips;
  OpponentPortrait = CreateWidget<US08TurnPortraitWidget>(World, US08TurnPortraitWidget::StaticClass());
  OwnPortrait = CreateWidget<US08TurnPortraitWidget>(World, US08TurnPortraitWidget::StaticClass());
  if (!OpponentPortrait || !OwnPortrait) {
    OpponentPortrait = OwnPortrait = nullptr;
    ArtHud.PendingTrace.Add(TEXT("HUD-TURN config portraits=0 reason=create-failed"));
    return;
  }
  OpponentPortrait->Setup(true, TurnHudLook, Chips.TeamChipColor(1));
  OwnPortrait->Setup(false, TurnHudLook, Chips.TeamChipColor(0));
  for (US08TurnPortraitWidget* Portrait : {OpponentPortrait.Get(), OwnPortrait.Get()}) {
    Portrait->SetVisibility(ESlateVisibility::Collapsed);  // shown with the live match HUD (TickTurnHud)
    Portrait->SetTrackerOpacity(Portrait->IsOpponent() ? 0.0f : 1.0f);
  }
  Canvas->AddSlot()
      .Anchors(FAnchors(0.0f, 1.0f))
      .Alignment(FVector2D(0.0f, 1.0f))
      .Offset(FMargin(GPortraitEdgeSu, -GPortraitEdgeSu, 0.0f, 0.0f))
      .AutoSize(true)
      [SAssignNew(TurnPortraitColumn, SVerticalBox).Visibility(EVisibility::SelfHitTestInvisible) +
       SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, GPortraitGapSu)[OpponentPortrait->TakeWidget()] +
       SVerticalBox::Slot().AutoHeight()[OwnPortrait->TakeWidget()]];
  // CUE-015: the banner of the own turn start (our decision, 01 F-07) - never a hit-test target
  Canvas->AddSlot()
      .Anchors(FAnchors(0.5f, 0.0f))
      .Alignment(FVector2D(0.5f, 0.0f))
      .Offset(FMargin(0.0f, GBannerTopSu, 0.0f, 0.0f))
      .AutoSize(true)
      [SAssignNew(TurnBanner, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(BannerSrgb(0x16, 0x1A, 0x28, 0.9f)))
           .Padding(FMargin(28.0f, 8.0f))
           .Visibility(EVisibility::Collapsed)
           [SNew(STextBlock)
                .Text(FText::FromString(TEXT("YOUR TURN")))
                .Font(FS08ArtHudFontToken(S08ArtHudFonts::CardTypeface, 30).Resolve())
                .ColorAndOpacity(FSlateColor(BannerSrgb(0xF2, 0xC1, 0x4E)))  // turn.flash.yellow
                .ShadowOffset(FVector2D(1.0f, 1.0f))
                .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f))]];
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-TURN config portraits=1 %s ringIcon=%d banner=%d"),
                                          *TurnHudLook.Describe(), OwnPortrait->HasRingIcon() ? 1 : 0,
                                          FMath::RoundToInt(FS09TurnCue::BannerMs)));
}

float AS08FlowGameMode::HandObstacleRightSu() const {
  if (!TurnPortraitColumn.IsValid() || !OwnPortrait || OwnPortrait->GetVisibility() == ESlateVisibility::Collapsed) {
    return 0.0f;
  }
  const float Width = TurnPortraitColumn->GetDesiredSize().X;
  return Width > 0.0f ? GPortraitEdgeSu + Width : 0.0f;
}

void AS08FlowGameMode::FeedTurnHud(const FS08Snapshot& Snapshot) {
  const FString ViewerId = ViewerIdNow();
  const double Now = static_cast<double>(NowMs());
  const FString TurnKey = FString::Printf(TEXT("%s#%d"), *Snapshot.CurrentTurnPlayerId, Snapshot.TurnCount);
  // the server marks are in ActionTracker (FeedOpponentView ran first); a new turn drops the local mark
  TrackerMarks.OnApplied(TurnKey, Snapshot.SequenceNumber, ActionTracker.Own().Spent);
  const FS09TurnCueEvent Event = TurnCue.OnApplied(Snapshot.CurrentTurnPlayerId, Snapshot.TurnCount, ViewerId,
                                                   Hud.bGameOver, Now, MoveMotion.bReducedMotion);
  if (!Event.bChanged) return;
  bTrackerResetPending = !Event.bGameOver;  // 01 F-12: both trackers snap in the frame the turn passes
  if (!OwnPortrait || !OpponentPortrait) return;
  US08TurnPortraitWidget* Active = Event.bGameOver ? nullptr : (Event.bOwn ? OwnPortrait.Get() : OpponentPortrait.Get());
  for (US08TurnPortraitWidget* Portrait : {OwnPortrait.Get(), OpponentPortrait.Get()}) {
    if (Portrait == Active) continue;
    Portrait->StopRing();
    Portrait->SetActive(false);
  }
  if (Active) {
    Active->PlayRing(Event.bInitial);
    Active->SetActive(true);
  }
  FS08Trace::Write(FString::Printf(
      TEXT("HUD-TURN seq=%d turn=%s initial=%d ring=%s flash=%d banner=%d reduced=%d"), Snapshot.SequenceNumber,
      Event.bGameOver ? TEXT("over") : (Event.bOwn ? TEXT("own") : TEXT("opp")), Event.bInitial ? 1 : 0,
      OwnPortrait->HasRingIcon() ? *TurnHudLook.RingIcon.ToString() : TEXT("none"),
      (Active && OwnPortrait->HasRingIcon() && !Event.bInitial && !MoveMotion.bReducedMotion)
          ? FMath::RoundToInt(FS09TurnCue::RingFlashMs)
          : 0,
      FMath::RoundToInt(TurnCue.BannerLengthMs()), MoveMotion.bReducedMotion ? 1 : 0));
  // Run E G-LIVE: one frame of the first own-turn banner, mid-way through its 600 ms
  if (bAutoS09 && !S09ShotDir.IsEmpty() && ShotBannerAtElapsed < 0.0f && Event.bOwn && !Event.bInitial &&
      !Event.bGameOver && TurnCue.BannerLengthMs() > 0.0) {
    ShotBannerAtElapsed = Elapsed + 0.25f;
  }
}

void AS08FlowGameMode::NoteActionChosen(const TCHAR* What) {
  if (!Hud.bViewerTurn || !Flow.IsValid()) return;
  const double Now = static_cast<double>(NowMs());
  const int32 Seq = Flow->GetAppliedSnapshot().SequenceNumber;
  TrackerMarks.Choose(ActionTracker.Own().Spent, Seq, Now);
  FS08Trace::Write(FString::Printf(TEXT("HUD-TRACK chosen=%s seq=%d spent=%d"), What, Seq, ActionTracker.Own().Spent));
}

void AS08FlowGameMode::TickTurnHud() {
  if (!OwnPortrait || !OpponentPortrait) return;
  const double Now = static_cast<double>(NowMs());
  // shown with the live match HUD; the result screen (DE-019 gate) takes the whole picture
  const bool bShow = Hud.bValid && !(Hud.bGameOver && ResultGate.IsShown());
  const ESlateVisibility Vis = bShow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed;
  for (US08TurnPortraitWidget* Portrait : {OwnPortrait.Get(), OpponentPortrait.Get()}) {
    if (Portrait->GetVisibility() != Vis) Portrait->SetVisibility(Vis);
  }
  if (TurnBanner.IsValid()) {
    const float Alpha = bShow ? TurnCue.BannerAlpha(Now) : 0.0f;
    const EVisibility BannerVis = Alpha > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
    if (TurnBanner->GetVisibility() != BannerVis) TurnBanner->SetVisibility(BannerVis);
    TurnBanner->SetRenderOpacity(Alpha);
  }
  if (!bShow) return;
  // run E review (acceptance defect 2): where the hand panel stands next to the portrait column
  if (const TSharedPtr<SWidget> Hand = ArtHud.HandPanel.Pin()) {
    const float CanvasW = HudCanvas.IsValid() ? HudCanvas->GetCachedGeometry().GetLocalSize().X : 0.0f;
    const float Column = HandObstacleRightSu();
    const float PanelW = Hand->GetDesiredSize().X;
    if (CanvasW > 0.0f && Column > 0.0f && PanelW > 0.0f) {
      const float Left = S09TurnHud::HandPanelLeft(CanvasW, PanelW, Column);
      const bool bShifted = Left > 0.5f * (CanvasW - PanelW) + 0.5f;
      const FString Key = FString::Printf(TEXT("%d|%.0f"), bShifted ? 1 : 0, Column);
      if (Key != HandLayoutTraceKey) {
        HandLayoutTraceKey = Key;
        FS08Trace::Write(FString::Printf(
            TEXT("HUD-HAND layout left=%.0f panel=%.0f canvas=%.0f columnRight=%.0f gutter=%.0f shifted=%d wrap=%.0f"),
            Left, PanelW, CanvasW, Column, S09TurnHud::HandGutterSu, bShifted ? 1 : 0,
            S09TurnHud::HandStripWrap(CanvasW, Column, 20.0f)));
      }
    }
  }

  // names, team colours, HP and the heart from the SHOWN fighters (the staging holds the HP to the contact)
  const FString ViewerId = ViewerIdNow();
  const FS08ArtHudPlateStyle Chips;
  auto FeedPortrait = [&](US08TurnPortraitWidget* Portrait, const FS09PlayerPanel* Panel, FS09HeartWatch& Heart) {
    if (!Panel) return;
    const FS08BoardFighter* Hero = nullptr;
    for (const FS08BoardFighter& F : HudFighters()) {
      if (F.OwnerId == Panel->PlayerId && F.bIsHero) {
        Hero = &F;
        break;
      }
    }
    Portrait->SetHeroName(PlayerHeroName(Panel->PlayerId));
    if (!Hero) return;
    Portrait->SetHealth(Hero->Health, Hero->MaxHealth);
    if (BoardActor) {
      const ES08TeamSlot Look = S08TeamLook(BoardActor->TeamOfFighter(*Hero), Hero->OwnerId == ViewerId,
                                            static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode));
      Portrait->SetTeamColor(Chips.TeamChipColor(Look == ES08TeamSlot::P1 ? 0 : 1));
    }
    const ES09HeartEvent HeartEvent = Heart.Sample(Hero->Id, Hero->Health);
    if (HeartEvent != ES09HeartEvent::None) {
      const bool bPlayed = Portrait->PlayHeart(S09TurnHud::HeartAnim(HeartEvent));
      FS08Trace::Write(FString::Printf(TEXT("HUD-HEART side=%s hero=%s hp=%d/%d anim=%s glow=%d played=%d"),
                                       Portrait->IsOpponent() ? TEXT("opp") : TEXT("own"), *Hero->Id, Hero->Health,
                                       Hero->MaxHealth, S09TurnHud::HeartEventName(HeartEvent),
                                       TurnHudLook.bHeartGlow ? 1 : 0, bPlayed ? 1 : 0));
    }
  };
  FeedPortrait(OwnPortrait, Hud.ViewerPanel(), OwnHeart);
  FeedPortrait(OpponentPortrait, Hud.OpponentPanel(), OpponentHeart);

  // trackers: mine with the action being chosen (01 F-12 "в момент выбора"), the opponent's only in their turn
  const FS09ActionTracker::FSlots Own = ActionTracker.Own();
  const bool bDraftOpen = Hud.bViewerTurn && (CommandUi.Mode == ES09CommandMode::AttackDraft ||
                                              CommandUi.Mode == ES09CommandMode::SchemeChoice);
  const int32 OwnShown = TrackerMarks.Shown(Own.Spent, Own.Slots, bDraftOpen, Now);
  const FS09ActionTracker::FSlots Opp = ActionTracker.Opponent();
  const bool bReset = bTrackerResetPending;
  const FString OwnAnim = OwnPortrait->ApplyTracker(Own.Slots, OwnShown, bReset);
  const FString OppAnim = OpponentPortrait->ApplyTracker(Opp.Slots, Opp.Spent, bReset);
  bTrackerResetPending = false;
  OwnPortrait->SetTrackerOpacity(1.0f);
  OpponentPortrait->SetTrackerOpacity(ActionTracker.OpponentAlpha(Now, MoveMotion.bReducedMotion));
  const FString Key = FString::Printf(TEXT("own=%d/%d server=%d local=%d opp=%d/%d oppVisible=%d"), OwnShown, Own.Slots,
                                      Own.Spent, OwnShown > Own.Spent ? 1 : 0, Opp.Spent, Opp.Slots,
                                      ActionTracker.OpponentVisible() ? 1 : 0);
  if (Key != TurnHudShownKey) {
    FS08Trace::Write(FString::Printf(TEXT("HUD-TRACK %s anim=%s/%s seq=%d frame=%llu"), *Key,
                                     OwnAnim.IsEmpty() ? TEXT("-") : *OwnAnim, OppAnim.IsEmpty() ? TEXT("-") : *OppAnim,
                                     Hud.SequenceNumber, static_cast<unsigned long long>(GFrameCounter)));
    TurnHudShownKey = Key;
  }
}

// ------------------------------------------------------------------------------------------------- gallery preview

void AS08FlowGameMode::GalleryPortraitsBegin(bool bFromBenchFixture) {
  UWorld* World = GetWorld();
  if (!World) return;
  TurnHudLook = FS08TurnHudLook::FromCommandLine(FCommandLine::Get());
  const FS08ArtHudPlateStyle Chips;
  // sample data of the review frame only (the live portraits read the server state)
  struct FSample {
    FString Name;
    int32 Hp;
    int32 MaxHp;
    bool bOpponent;
    int32 Chip;  // FS08ArtHudPlateStyle::TeamChipColor index
  };
  TArray<FSample> Samples = {{TEXT("Medusa"), 15, 15, true, 1}, {TEXT("King Arthur"), 16, 18, false, 0}};
  if (bFromBenchFixture) {
    // DE-028: the bench fixture's heroes - the viewer's below, the other above - in the live team look (TickTurnHud)
    const FS08BoardFighter* Own = nullptr;
    const FS08BoardFighter* Opp = nullptr;
    for (const FS08BoardFighter& F : Fighters) {
      if (!F.bIsHero) continue;
      if (F.OwnerId == BenchViewerId) {
        if (!Own) Own = &F;
      } else if (!Opp) {
        Opp = &F;
      }
    }
    auto Chip = [&](const FS08BoardFighter& F, bool bOpponent) {
      if (!BoardActor) return bOpponent ? 1 : 0;
      const ES08TeamSlot Look = S08TeamLook(BoardActor->TeamOfFighter(F), F.OwnerId == BenchViewerId,
                                            static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode));
      return Look == ES08TeamSlot::P1 ? 0 : 1;
    };
    auto Name = [](const FS08BoardFighter& F) { return F.Label.IsEmpty() ? F.Name : F.Label; };
    if (Own && Opp) {
      Samples = {{Name(*Opp), Opp->Health, Opp->MaxHealth, true, Chip(*Opp, true)},
                 {Name(*Own), Own->Health, Own->MaxHealth, false, Chip(*Own, false)}};
    }
  }
  // the same column as the live HUD (BuildTurnHudWidgets), above the gallery (z 1000)
  TSharedRef<SVerticalBox> Column = SNew(SVerticalBox).Visibility(EVisibility::SelfHitTestInvisible);
  for (const FSample& S : Samples) {
    US08TurnPortraitWidget* Portrait = CreateWidget<US08TurnPortraitWidget>(World, US08TurnPortraitWidget::StaticClass());
    if (!Portrait) return;
    Portrait->Setup(S.bOpponent, TurnHudLook, Chips.TeamChipColor(S.Chip));
    Portrait->SetHeroName(S.Name);
    Portrait->SetHealth(S.Hp, S.MaxHp);
    Portrait->SetActive(!S.bOpponent);
    // over the board it is my turn: the opponent's tracker is hidden as in the live HUD (DE-022 / DE-023)
    if (bFromBenchFixture && S.bOpponent) Portrait->SetTrackerOpacity(0.0f);
    Column->AddSlot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, S.bOpponent ? GPortraitGapSu : 0.0f)[Portrait->TakeWidget()];
    GalleryPortraits.Add(Portrait);
  }
  if (GEngine && GEngine->GameViewport) {
    TSharedRef<SConstraintCanvas> Canvas = SNew(SConstraintCanvas);
    Canvas->AddSlot()
        .Anchors(FAnchors(0.0f, 1.0f))
        .Alignment(FVector2D(0.0f, 1.0f))
        .Offset(FMargin(GPortraitEdgeSu, -GPortraitEdgeSu, 0.0f, 0.0f))
        .AutoSize(true)[Column];
    GEngine->GameViewport->AddViewportWidgetContent(Canvas, 2000);  // AddToViewport(1000) sits at 1000 + 10
  }
  FS08Trace::Write(FString::Printf(TEXT("%s portraits=%d own=%s opp=%s %s"),
                                   bFromBenchFixture ? TEXT("BENCH turn-hud") : TEXT("ICONGALLERY"), GalleryPortraits.Num(),
                                   *Samples.Last().Name.Replace(TEXT(" "), TEXT("_")),
                                   *Samples[0].Name.Replace(TEXT(" "), TEXT("_")), *TurnHudLook.Describe()));
}

void AS08FlowGameMode::GalleryPortraitsAt(float TMs) {
  for (US08TurnPortraitWidget* Portrait : GalleryPortraits) {
    if (!Portrait) continue;
    // replay from 0: mine starts its turn (ring appear), spends one slot and takes a hit; the opponent's portrait shows
    // a spent slot at rest (its turn's tracker as it would look)
    Portrait->SetClockOverrideMs(0.0f);
    if (!Portrait->IsOpponent()) {
      Portrait->PlayRing(false);
      Portrait->ApplyTracker(2, 0, true);
      Portrait->ApplyTracker(2, 1, false);
      if (Portrait->GetHeartIcon()) Portrait->GetHeartIcon()->ShowAtRest();
      Portrait->PlayHeart(TEXT("damage"));
    } else {
      Portrait->StopRing();
      Portrait->ApplyTracker(2, 1, true);
    }
    Portrait->SetClockOverrideMs(TMs);
  }
}

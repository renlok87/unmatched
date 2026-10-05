// DE-026 (W-18; de-footage/task 01 F-10, D-DE-10; 02 SD-02, SD-26, SD-28 п. 4, SD-54; 07-animation-vfx-audio CUE-006):
// the hand and the played cards in the game mode (the world-free models: S09/S09CardSlot.h).
//   - The source-card slot at the top left, under the command panel (02-ux-ui-spec §4.6 п. 4): the played scheme with
//     the SCHEME ribbon, the opponent's maneuver boost with BOOSTED (SD-54), the opponent's discards with DISCARDED.
//     The ribbons are Slate bands (the marker-status art is not in UE); the card is the UI-CARD-FRAME fallback of
//     CUE-006 (there is no 3D card plane). The widget is hit-test invisible: a click on it is a click on the field.
//   - The opponent's scheme (F-10): fly 200 -> 1500 ms BEFORE its effect. Meanwhile the board and the HUD keep the
//     fighters of the previous snapshot (positions, HP, statuses), the cues of its seq wait, my own choice it opened
//     waits with the command panel collapsed, and the last-move highlight is not revealed. A click on the field,
//     Space or Enter starts the effect at once ('INPUT slot-skip'); in my own turn the click still reaches the field
//     (DE-015: input opens with the turn). Run E review: the rest of the same scheme (its pending effects resolved in
//     the next seqs, a quiet seq) joins the hold; a new action (a maneuver, an attack, another card) or the end of the
//     game releases it and its held moves still play - joined with the new seq's own moves (one path per fighter);
//     the card keeps its read time. A reset drops everything. My own scheme never waits.
//   - The card stays while its effect runs (a move plays, a choice is open) and leaves - a scheme in one frame, a boost
//     or a discard with a 250 ms fade.
//   - SD-26: while a cell or a target is picked on the board and the cursor is not over the HUD, the hand panel slides
//     60 slate units down and the hand-card inspector is not drawn.
// Trace: 'HUD-SLOT config|show|effect|off|drop|cues|choice ...', 'INPUT slot-skip src=... seq=...',
// 'HUD-HAND lower=<0|1> pick=... cursor=... preview=...'.
#include "S08FlowGameMode.h"

#include "S08BoardActor.h"
#include "S08TraceLog.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Text/STextBlock.h"

namespace {
/** The slot's gap to the left edge and under the command panel (slate units). */
constexpr float GSlotLeftSu = 16.0f;
constexpr float GSlotGapSu = 12.0f;
constexpr float GSlotWidthSu = 260.0f;
/** Where the card flies in from, relative to its slot (slate units): mine from the hand below, the opponent's from
 *  the left edge (the top-left corner is the opponent's side of the HUD). */
const FVector2D GOwnFlyFrom(120.0f, 360.0f);
const FVector2D GOppFlyFrom(-320.0f, 0.0f);

FLinearColor SlotSrgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}

/** Ribbon colours - off the S09 state markers (#FF00FF, #00FFFF, #A020FF ...): scheme blue, boost gold, discard grey. */
FLinearColor RibbonColor(ES09SlotRibbon Ribbon) {
  switch (Ribbon) {
    case ES09SlotRibbon::Boosted: return SlotSrgb(0xC8, 0x96, 0x28);
    case ES09SlotRibbon::Discarded: return SlotSrgb(0x6E, 0x6E, 0x76);
    default: return SlotSrgb(0x2E, 0x6C, 0xB4);
  }
}

FString ValueLine(const FS09SlotCard& Slot) {
  const FS09CardView& Card = Slot.Card;
  if (Slot.Ribbon == ES09SlotRibbon::Boosted) {
    return FString::Printf(TEXT("BOOST +%d"), Card.bHasBoostValue ? Card.BoostValue : 0);
  }
  if (Card.CardType == TEXT("SCHEME")) return TEXT("SCHEME");
  TArray<FString> Parts;
  if (Card.AttackValue > 0) Parts.Add(FString::Printf(TEXT("ATTACK %d"), Card.AttackValue));
  if (Card.DefenseValue > 0) Parts.Add(FString::Printf(TEXT("DEFENSE %d"), Card.DefenseValue));
  if (Card.bHasBoostValue) Parts.Add(FString::Printf(TEXT("BOOST %d"), Card.BoostValue));
  return Parts.Num() > 0 ? FString::Join(Parts, TEXT("  |  ")) : Card.CardType;
}
}  // namespace

void AS08FlowGameMode::BuildCardSlotWidgets(const TSharedRef<SConstraintCanvas>& Canvas) {
  // BuildUi runs before the trace opens: the line waits in ArtHud.PendingTrace like the other HUD config lines.
  ArtHud.PendingTrace.Add(FString::Printf(
      TEXT("HUD-SLOT config fly=%d oppHold=%d own=%d min=%d fade=%d cap=%d lowerSu=%.0f slide=%.0f"),
      FS09SourceSlot::FlyMs, FS09SourceSlot::OppSchemeHoldMs, FS09SourceSlot::OwnSchemeMs, FS09SourceSlot::MinShowMs,
      FS09SourceSlot::FadeMs, FS09SourceSlot::MaxShowMs, FS09HandLower::LowerSu, FS09HandLower::SlideMs));
  Canvas->AddSlot()
      .Anchors(FAnchors(0.0f, 0.0f))
      .Alignment(FVector2D(0.0f, 0.0f))
      .Offset(TAttribute<FMargin>::CreateLambda([this]() {
        // under the command panel (top left); straight at the top while the panel is collapsed by a held scheme
        float Below = 0.0f;
        if (const TSharedPtr<SWidget> Panel = ArtHud.CommandPanel.Pin()) {
          if (Panel->GetVisibility() != EVisibility::Collapsed) Below = Panel->GetCachedGeometry().GetLocalSize().Y;
        }
        return FMargin(GSlotLeftSu, Below + GSlotGapSu, 0.0f, 0.0f);
      }))
      .AutoSize(true)
      [SAssignNew(CardSlotBox, SBox).Visibility(EVisibility::Collapsed)];
}

void AS08FlowGameMode::RebuildCardSlotWidget() {
  if (!CardSlotBox.IsValid()) return;
  CardSlotBuiltRevision = CardSlot.GetRevision();
  bCardSlotBuiltHolding = CardSlot.HoldsEffect();
  if (!CardSlot.IsVisible()) {
    CardSlotBox->SetContent(SNullWidget::NullWidget);
    return;
  }
  const FS09SlotCard& Slot = CardSlot.GetCard();
  const FS09CardView& Card = Slot.Card;
  const FLinearColor Accent = RibbonColor(Slot.Ribbon);
  TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
  const FString Ribbon = Slot.Count > 1 ? FString::Printf(TEXT("%s  x%d"), S09SlotRibbonLabel(Slot.Ribbon), Slot.Count)
                                        : FString(S09SlotRibbonLabel(Slot.Ribbon));
  Box->AddSlot().AutoHeight().Padding(0, 0, 0, 6)
      [SNew(SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(Accent))
           .Padding(FMargin(10.0f, 3.0f))
           [SNew(STextBlock).Text(FText::FromString(Ribbon))
                .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
                .ColorAndOpacity(FSlateColor(FLinearColor::White))]];
  Box->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
      [SNew(STextBlock)
           .Text(FText::FromString(FString::Printf(TEXT("%s - %s"), Slot.bOpponent ? TEXT("OPPONENT") : TEXT("YOU"),
                                                   *PlayerHeroName(Slot.OwnerId))))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
           .ColorAndOpacity(FSlateColor(FLinearColor(0.78f, 0.78f, 0.84f, 1.0f)))];
  Box->AddSlot().AutoHeight()
      [SNew(STextBlock).Text(FText::FromString(Card.Name))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 18))
           .WrapTextAt(GSlotWidthSu - 24.0f)];
  Box->AddSlot().AutoHeight().Padding(0, 2)
      [SNew(STextBlock).Text(FText::FromString(ValueLine(Slot)))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
           .ColorAndOpacity(FSlateColor(Accent))];
  if (!Card.BannerName.IsEmpty()) {
    Box->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(Card.BannerName))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
             .ColorAndOpacity(FSlateColor(FLinearColor(0.75f, 0.75f, 0.8f, 1.0f)))];
  }
  if (!Card.Text.IsEmpty()) {
    Box->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(STextBlock).Text(FText::FromString(Card.Text))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
             .WrapTextAt(GSlotWidthSu - 24.0f)];
  }
  if (bCardSlotBuiltHolding) {
    // F-10: the effect waits for the read; the skip is a click on the field, Space or Enter
    Box->AddSlot().AutoHeight().Padding(0, 8, 0, 0)
        [SNew(STextBlock).Text(FText::FromString(TEXT("click, Space or Enter - play the effect now")))
             .Font(FCoreStyle::GetDefaultFontStyle("Italic", 12))
             .ColorAndOpacity(FSlateColor(FLinearColor(0.85f, 0.85f, 0.65f, 1.0f)))];
  }
  CardSlotBox->SetContent(
      SNew(SBorder)
          .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
          .BorderBackgroundColor(FSlateColor(FLinearColor(0.02f, 0.025f, 0.05f, 0.92f)))
          .Padding(12.0f)
          [SNew(SBox).WidthOverride(GSlotWidthSu)[Box]]);
}

void AS08FlowGameMode::FeedCardSlot(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& FightersBefore) {
  const int64 Now = NowMs();
  TArray<FString> Lines;
  auto Flush = [&Lines]() {
    for (const FString& Line : Lines) FS08Trace::Write(Line);
    Lines.Reset();
  };
  const bool bPrevQueueOpen = bCardSlotQueueOpen;
  const TArray<FS08PendingEffect> Queue = S09OpponentView::PendingQueue(Snapshot);
  bCardSlotQueueOpen = Queue.Num() > 0;
  FS09LastMovement Trail;
  FS09LastMovement::Read(Snapshot.Metadata, Trail);
  FS09SlotCard Card;
  const bool bCard = PlayedCards.OnApplied(Hud, Queue, Trail, ViewerIdNow(), Card);
  // Run E review (DE-026): a newer seq while the opponent's scheme waits. The rest of that scheme (its pending
  // effects resolved one seq at a time - the VS_AI bot publishes them with no pause - or a quiet seq) joins the hold;
  // a new action (a maneuver, an attack, another card) starts the held effect now and its moves play with the new
  // seq's own (never dropped).
  if (CardSlot.HoldsEffect() && !CardSlot.InChain(Snapshot.SequenceNumber)) {
    FS09SchemeChainStep Step;
    Step.OwnerId = CardSlot.GetCard().OwnerId;
    Step.Seq = Snapshot.SequenceNumber;
    Step.bCombat = FS09PlayedCardWatch::IsCombatPhase(Snapshot.Phase);
    Step.bNewCard = bCard && Card.Ribbon != ES09SlotRibbon::Discarded;
    Step.bPrevQueueOpen = bPrevQueueOpen;
    Step.bFightersChanged = FightersBefore.Num() != Fighters.Num();
    for (const FS08BoardFighter& After : Fighters) {
      if (Step.bFightersChanged) break;
      const FS08BoardFighter* Before = FightersBefore.FindByPredicate(
          [&After](const FS08BoardFighter& Entry) { return Entry.Id == After.Id; });
      Step.bFightersChanged = !Before || Before->X != After.X || Before->Y != After.Y ||
                              Before->Health != After.Health || Before->bDefeated != After.bDefeated;
    }
    Step.Trail = Trail;
    if (const TCHAR* Why = S09SchemeChainContinues(Step)) {
      CardSlot.ContinueChain(Snapshot.SequenceNumber, Why, Lines);
      Flush();
    } else if (CardSlot.ReleaseForSeq(Snapshot.SequenceNumber, Now, Lines)) {
      Flush();
      OnCardSlotReleased(/*bPlayCues=*/true, TEXT("newseq"), Snapshot.SequenceNumber);
    }
  }
  if (bCard) {
    bool bReleased = false;
    const bool bShown = CardSlot.Show(Card, Now, MoveMotion.bReducedMotion, Lines, bReleased);
    Flush();
    if (bReleased) OnCardSlotReleased(/*bPlayCues=*/true, TEXT("replace"), Snapshot.SequenceNumber);
    if (bShown && CardSlot.HoldsEffect()) {
      SlotHeldFighters = FightersBefore;  // the HUD and the board keep these until the effect is due
      SlotHeldCues.Reset();
    }
    // Run E G-LIVE: one frame of the first card per owner, after its 200 ms fly-in
    if (bShown && bAutoS09 && !S09ShotDir.IsEmpty()) {
      float& At = Card.bOpponent ? ShotSlotOppAtElapsed : ShotSlotOwnAtElapsed;
      if (At < 0.0f) At = Elapsed + 0.45f;
    }
  }
  if (Hud.bGameOver && CardSlot.IsVisible()) {
    bool bReleased = false;
    CardSlot.Cut(Now, TEXT("gameover"), Lines, bReleased);
    Flush();
    // the game is over: the held moves and damage still play under the result (nothing of the board is lost)
    if (bReleased) OnCardSlotReleased(/*bPlayCues=*/true, TEXT("gameover"), Snapshot.SequenceNumber);
  }
}

bool AS08FlowGameMode::HoldCardSlotCues(const TArray<FS08Cue>& Cues) {
  if (Cues.Num() == 0 || !CardSlot.InChain(Cues[0].SequenceNumber)) return false;
  SlotHeldCues.Append(Cues);
  FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT cues held seq=%d of=%d n=%d total=%d"), Cues[0].SequenceNumber,
                                   CardSlot.HeldSeq(), Cues.Num(), SlotHeldCues.Num()));
  return true;
}

bool AS08FlowGameMode::TakeCardSlotCarry(const TArray<FS08Cue>& Cues, TArray<FS08Cue>& OutJoined) {
  if (SlotCarryCues.Num() == 0) return false;
  if (Cues.Num() == 0 || Cues[0].SequenceNumber != SlotCarrySeq) {
    FlushCardSlotCarry();  // another seq: the carried moves play on their own first
    return false;
  }
  TArray<FS08Cue> All = MoveTemp(SlotCarryCues);
  SlotCarryCues.Reset();
  SlotCarrySeq = -1;
  const int32 Carried = All.Num();
  All.Append(Cues);
  OutJoined = S09MergeHeldCues(All);
  FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT cues joined seq=%d carried=%d new=%d play=%d"),
                                   Cues[0].SequenceNumber, Carried, Cues.Num(), OutJoined.Num()));
  return true;
}

void AS08FlowGameMode::FlushCardSlotCarry() {
  if (SlotCarryCues.Num() == 0) return;
  TArray<FS08Cue> Carry = S09MergeHeldCues(SlotCarryCues);
  FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT cues flushed seq=%d n=%d"), SlotCarrySeq, Carry.Num()));
  SlotCarryCues.Reset();
  SlotCarrySeq = -1;
  HandleCues(Carry);
}

void AS08FlowGameMode::ApplyCardSlotHold(TArray<FS08BoardFighter>& View) const {
  if (!CardSlot.HoldsEffect() || SlotHeldFighters.Num() == 0) return;
  for (FS08BoardFighter& Fighter : View) {
    const FS08BoardFighter* Before = SlotHeldFighters.FindByPredicate(
        [&Fighter](const FS08BoardFighter& Entry) { return Entry.Id == Fighter.Id; });
    if (!Before) continue;
    Fighter.X = Before->X;
    Fighter.Y = Before->Y;
    Fighter.Health = Before->Health;
    Fighter.bDefeated = Before->bDefeated;
    Fighter.Effects = Before->Effects;
  }
}

void AS08FlowGameMode::OnCardSlotReleased(bool bPlayCues, const TCHAR* Why, int32 CarryToSeq) {
  SlotHeldFighters.Reset();
  TArray<FS08Cue> Cues = MoveTemp(SlotHeldCues);
  SlotHeldCues.Reset();
  if (bCardSlotHidesChoice) {
    bCardSlotHidesChoice = false;
    if (const TSharedPtr<SWidget> Panel = ArtHud.CommandPanel.Pin()) Panel->SetVisibility(EVisibility::Visible);
    FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT choice hidden=0 why=%s"), Why));
  }
  RefreshShownFighters(/*bSyncBoard=*/true);  // the board and the HUD go to the snapshot
  if (Cues.Num() > 0) {
    const bool bCarry = bPlayCues && CarryToSeq >= 0;
    const FString CarryNote = bCarry ? FString::Printf(TEXT(" carry=%d"), CarryToSeq) : FString();
    FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT cues %s seq=%d n=%d why=%s%s"),
                                     bPlayCues ? TEXT("play") : TEXT("dropped"), Cues[0].SequenceNumber, Cues.Num(), Why,
                                     *CarryNote));
    if (bCarry) {
      // released inside the apply of a newer seq: its own cues come right after - the held moves are joined with
      // them (one path per fighter), or play alone from the next frame if it brings none
      SlotCarryCues.Append(Cues);
      SlotCarrySeq = CarryToSeq;
    } else if (bPlayCues) {
      HandleCues(S09MergeHeldCues(Cues));  // the moves start from the frame of the release (CUE-007)
    }
  }
  RefreshHud();
}

bool AS08FlowGameMode::TryCardSlotSkip() {
  if (!CardSlot.HoldsEffect()) return false;
  auto* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || ArtView.IsValid()) return false;
  const bool bWasHidingChoice = bCardSlotHidesChoice;
  // 01 F-10: a click on the field, Space or Enter start the effect at once (HUD buttons keep their own action)
  const TCHAR* Source = nullptr;
  if (PC->WasInputKeyJustPressed(EKeys::LeftMouseButton) && ViewportHasFocus() && !HudPress->IsPressed()) {
    Source = TEXT("click");
  } else if (PC->WasInputKeyJustPressed(EKeys::SpaceBar)) {
    Source = TEXT("space");
  } else if (PC->WasInputKeyJustPressed(EKeys::Enter)) {
    Source = TEXT("enter");
  }
  bool bSkipped = false;
  if (Source) {
    TArray<FString> Lines;
    const int32 Seq = CardSlot.HeldSeq();
    if (CardSlot.Skip(NowMs(), Source, Lines)) {
      bSkipped = true;
      CombatSkipFrame = GFrameCounter;  // the same Space is not a camera / move skip too
      FS08Trace::Write(FString::Printf(TEXT("INPUT slot-skip src=%s seq=%d"), Source, Seq));
      for (const FString& Line : Lines) FS08Trace::Write(Line);
      OnCardSlotReleased(/*bPlayCues=*/true, Source);
    }
  }
  // my own choice was hidden behind the hold: nothing else may act on it this frame; in the opponent's turn the skip
  // click meant only "continue"; in my turn the click goes on to the field (DE-015)
  return bWasHidingChoice || (bSkipped && !Hud.bViewerTurn);
}

bool AS08FlowGameMode::CursorOverHud() const {
  const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  float X = 0.0f, Y = 0.0f;
  if (!PC || !PC->GetMousePosition(X, Y)) return false;  // no OS cursor (offscreen): the pick is over the field
  auto Inside = [X, Y](const FS08ScreenRect& R) { return X >= R.X0 && X <= R.X1 && Y >= R.Y0 && Y <= R.Y1; };
  for (const TWeakPtr<SWidget>& Panel : {ArtHud.CommandPanel, ArtHud.SidePanel}) {
    FS08ScreenRect R;
    if (WidgetViewportRect(Panel.Pin(), R) && Inside(R)) return true;
  }
  FS08ScreenRect Hand;
  if (WidgetViewportRect(ArtHud.HandPanel.Pin(), Hand)) {
    // the lowered hand counts with its raised rectangle: no flicker when the cursor rests at its top edge
    if (HandLower.IsLowered()) Hand.Y0 -= 2.0f * FS09HandLower::LowerSu;
    if (Inside(Hand)) return true;
  }
  return false;
}

void AS08FlowGameMode::TickCardSlot() {
  const int64 Now = NowMs();
  const bool bReduced = MoveMotion.bReducedMotion;
  FlushCardSlotCarry();  // the newer seq that released a held scheme brought no cues of its own
  // ---- the slot: the effect runs while a move plays or a choice is open
  {
    const bool bBusy = (BoardActor && BoardActor->AnyFighterMoving()) || bCardSlotQueueOpen;
    TArray<FString> Lines;
    bool bReleased = false;
    CardSlot.Tick(Now, bBusy, Lines, bReleased);
    for (const FString& Line : Lines) FS08Trace::Write(Line);
    if (bReleased) OnCardSlotReleased(/*bPlayCues=*/true, TEXT("time"));
  }
  // my own choice opened by the held opponent's scheme waits with it (the command panel collapses for the hold)
  const bool bHide = CardSlot.HoldsEffect() && (CommandUi.Mode == ES09CommandMode::PendingChoice ||
                                                CommandUi.Mode == ES09CommandMode::DiscardDraft);
  if (bHide != bCardSlotHidesChoice) {
    bCardSlotHidesChoice = bHide;
    if (const TSharedPtr<SWidget> Panel = ArtHud.CommandPanel.Pin()) {
      Panel->SetVisibility(bHide ? EVisibility::Collapsed : EVisibility::Visible);
    }
    FS08Trace::Write(FString::Printf(TEXT("HUD-SLOT choice hidden=%d seq=%d mode=%d"), bHide ? 1 : 0,
                                     CardSlot.HeldSeq(), static_cast<int32>(CommandUi.Mode)));
  }
  if (CardSlotBox.IsValid()) {
    if (CardSlot.GetRevision() != CardSlotBuiltRevision || CardSlot.HoldsEffect() != bCardSlotBuiltHolding) {
      RebuildCardSlotWidget();
    }
    const bool bVisible = CardSlot.IsVisible() && Hud.bValid && !IsResultScreenShown();
    const EVisibility Vis = bVisible ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
    if (CardSlotBox->GetVisibility() != Vis) CardSlotBox->SetVisibility(Vis);
    if (bVisible) {
      const FVector2D From = (CardSlot.GetCard().bOpponent ? GOppFlyFrom : GOwnFlyFrom) * (1.0f - CardSlot.FlyT(Now));
      CardSlotBox->SetRenderTransform(FSlateRenderTransform(FVector2f(static_cast<float>(From.X), static_cast<float>(From.Y))));
      CardSlotBox->SetRenderOpacity(CardSlot.Alpha(Now));
    }
  }
  // ---- SD-26: the hand goes down while a cell or a target is picked on the field
  const ES09BoardPick Pick =
      Hud.bValid && !Hud.bGameOver ? S09BoardPickOf(CommandUi, Hud.bViewerTurn) : ES09BoardPick::None;
  const FString HandLine = HandLower.Update(Pick, Pick != ES09BoardPick::None && CursorOverHud(), static_cast<double>(Now));
  if (!HandLine.IsEmpty()) FS08Trace::Write(FString::Printf(TEXT("%s seq=%d"), *HandLine, Hud.SequenceNumber));
  const float Offset = HandLower.OffsetSu(static_cast<double>(Now), bReduced);
  if (!FMath::IsNearlyEqual(Offset, HandOffsetApplied, 0.05f)) {
    HandOffsetApplied = Offset;
    if (const TSharedPtr<SWidget> Hand = ArtHud.HandPanel.Pin()) {
      Hand->SetRenderTransform(FSlateRenderTransform(FVector2f(0.0f, Offset)));
    }
  }
  if (HandLower.HidesPreview() != bHandPreviewHidden) {
    bHandPreviewHidden = HandLower.HidesPreview();
    if (bInspecting && InspectedSource == 0) RefreshHud();  // the hand-card inspector hides / comes back
  }
}

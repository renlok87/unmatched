// DE-030 (W-19; 01 F-05, D-DE-05; 02 SD-29, SD-41; 02-ux-ui-spec §4.7 UI-HUD-DECKS "Панель «Колода»"): the deck side
// panel of the game mode.
//   - A side panel at the right edge over the side counters; the field stays visible (DE hides it behind a full
//     screen - we do not). It opens for the own deck (K / "YOUR DECK") and for the opponent's (Shift+K / "OPP DECK").
//   - The persistent canvas slot is built once (BuildDeckPanelWidgets); RefreshHud fills its content, the tick drives
//     its opacity: open 80 ms (<= 100), close 150 ms (S09/S09DeckPanel.h FS09DeckPanelView).
//   - It closes by itself on an event that asks me for input: my turn starts, my defense window, my deferred choice,
//     my hand-limit discard, GAME_OVER (S09DeckPanel::InputDemandKey).
//   - Data: the public deck lists of the match (FS08FlowController::EnsureDeckLists - backend gameDeckLists), my hand
//     and both public discard piles of the HUD model. The order of a deck and the opponent's hand never reach the
//     client (QA-005): his hand is a row of card backs by number.
// Trace: 'DECK panel open|close side=... why=...' and 'DECK model ...' (counts only, no card name).
// Review tooling: -Bench -BenchDeckPanel=own|opp -BenchDeckLists=<gameDeckLists answer .json> lays the panel over the
// bench scene on a real map.
#include "S08FlowGameMode.h"

#include "S08ArtHudStyle.h"
#include "S08TraceLog.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Styling/CoreStyle.h"
#include "UnrealClient.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace {
constexpr float GDeckPanelWidthSu = 400.0f;

FLinearColor DeckSrgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}

FSlateFontInfo DeckCardFont(int32 Size) { return FS08ArtHudFontToken(S08ArtHudFonts::CardTypeface, Size).Resolve(); }

/** The type stripe of a row (our palette - DE's card art is not copied). */
FLinearColor TypeTint(const FString& Type) {
  if (Type == TEXT("ATTACK")) return DeckSrgb(0xC0, 0x4A, 0x3E);
  if (Type == TEXT("DEFENSE")) return DeckSrgb(0x3E, 0x78, 0xC0);
  if (Type == TEXT("SCHEME")) return DeckSrgb(0xD8, 0xB0, 0x3C);
  return DeckSrgb(0x8A, 0x5C, 0xC0);  // VERSATILE / UNIVERSAL
}

FString ValuesText(const FS09DeckListCard& Card) {
  FString Out;
  if (Card.AttackValue >= 0) Out += FString::Printf(TEXT("A%d "), Card.AttackValue);
  if (Card.DefenseValue >= 0) Out += FString::Printf(TEXT("D%d "), Card.DefenseValue);
  if (Card.BoostValue >= 0) Out += FString::Printf(TEXT("B%d"), Card.BoostValue);
  return Out.TrimEnd();
}

/** A small mark chip ("IN HAND 1"). */
TSharedRef<SWidget> MarkChip(const FString& Text, const FLinearColor& Back, const FLinearColor& Fore) {
  return SNew(SBorder)
      .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
      .BorderBackgroundColor(FSlateColor(Back))
      .Padding(FMargin(5.0f, 1.0f))
      [SNew(STextBlock).Text(FText::FromString(Text)).Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
           .ColorAndOpacity(FSlateColor(Fore))];
}
}  // namespace

void AS08FlowGameMode::BuildDeckPanelWidgets(const TSharedRef<SConstraintCanvas>& Canvas) {
  // over the side counters (added after them), under the result screen (added before it)
  Canvas->AddSlot()
      .Anchors(FAnchors(1.0f, 0.0f))
      .Alignment(FVector2D(1.0f, 0.0f))
      .Offset(FVector2D(0.0f, 0.0f))
      .AutoSize(true)
      [SAssignNew(DeckPanelBorder, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(DeckSrgb(0x0B, 0x0E, 0x18, 1.0f)))
           .Padding(FMargin(14.0f, 12.0f))
           .Visibility(EVisibility::Collapsed)
           [SNew(SBox)
                // at least as wide as the side counters it covers (they share the right edge): nothing peeks out
                .WidthOverride(TAttribute<FOptionalSize>::CreateLambda([this]() -> FOptionalSize {
                  const TSharedPtr<SWidget> Side = ArtHud.SidePanel.Pin();
                  const float SideW = Side.IsValid() ? Side->GetDesiredSize().X - 28.0f : 0.0f;
                  return FMath::Max(GDeckPanelWidthSu, SideW);
                }))
                .MaxDesiredHeight(TAttribute<FOptionalSize>::CreateLambda([]() -> FOptionalSize {
                  if (GEngine && GEngine->GameViewport) {
                    const TSharedPtr<SWidget> ViewportWidget = GEngine->GameViewport->GetGameViewportWidget();
                    if (ViewportWidget.IsValid()) {
                      const float H = ViewportWidget->GetCachedGeometry().GetLocalSize().Y;
                      if (H > 0.0f) return FMath::Max(200.0f, H - 48.0f);
                    }
                  }
                  return 600.0f;
                }))
                [SAssignNew(DeckPanelBox, SBox)]]];
}

FString AS08FlowGameMode::DeckDemandKeyNow() const {
  const FString ViewerId = ViewerIdNow();
  FS09DeckDemandInput In;
  In.bGameOver = Hud.bGameOver;
  In.bViewerTurn = Hud.bViewerTurn;
  In.TurnCount = Hud.TurnCount;
  In.bViewerDefends = CommandUi.Combat.bPresent && Hud.Phase == TEXT("COMBAT") && !ViewerId.IsEmpty() &&
                      CommandUi.Combat.DefenderId == ViewerId;
  In.CombatKey = CommandUi.Combat.AttackerId + TEXT(">") + CommandUi.Combat.TargetFighterId;
  if (CommandUi.PendingQueue.Num() > 0 && !ViewerId.IsEmpty() && CommandUi.PendingQueue[0].PlayerId == ViewerId) {
    In.OwnPendingId = CommandUi.PendingQueue[0].Id.IsEmpty() ? FString(TEXT("head")) : CommandUi.PendingQueue[0].Id;
  }
  if (Hud.bHasPendingDiscard && (Hud.PendingDiscard.PlayerId.IsEmpty() || Hud.PendingDiscard.PlayerId == ViewerId)) {
    In.OwnDiscardId = Hud.PendingDiscard.Id.IsEmpty() ? FString(TEXT("hand")) : Hud.PendingDiscard.Id;
  }
  return S09DeckPanel::InputDemandKey(In);
}

void AS08FlowGameMode::ToggleDeckPanel(ES09DeckSide Side, const TCHAR* Why) {
  const int64 Now = NowMs();
  const bool bWasOpen = DeckPanel.IsOpen();
  const bool bOpened = DeckPanel.Toggle(Side, Now, DeckDemandKeyNow());
  if (bOpened) {
    DeckPanelSelected.Reset();
    // the list is fetched once per match; the panel's open retries a failed fetch
    if (Flow.IsValid()) Flow->EnsureDeckLists(/*bRetryFailed=*/true);
    FS08Trace::Write(FString::Printf(TEXT("DECK panel open side=%s t=%lld fade=%d why=%s%s"),
                                     S09DeckPanel::SideName(Side), static_cast<long long>(Now),
                                     bWasOpen ? 0 : FS09DeckPanelView::OpenMs, Why, bWasOpen ? TEXT(" switch=1") : TEXT("")));
  } else if (bWasOpen && !DeckPanel.IsOpen()) {
    FS08Trace::Write(FString::Printf(TEXT("DECK panel close side=%s t=%lld fade=%d why=%s"),
                                     S09DeckPanel::SideName(Side), static_cast<long long>(Now), FS09DeckPanelView::CloseMs,
                                     Why));
  }
  DeckModelTraced.Reset();
  RefreshHud();
  TickDeckPanel();
}

void AS08FlowGameMode::CloseDeckPanel(const TCHAR* Why) {
  const int64 Now = NowMs();
  if (!DeckPanel.Close(Now)) return;
  FS08Trace::Write(FString::Printf(TEXT("DECK panel close side=%s t=%lld fade=%d why=%s"),
                                   S09DeckPanel::SideName(DeckPanel.Side()), static_cast<long long>(Now),
                                   FS09DeckPanelView::CloseMs, Why));
  TickDeckPanel();
}

bool AS08FlowGameMode::HandleDeckPanelKeys(APlayerController* PC) {
  if (!PC) return false;
  if (DeckPanel.IsOpen() && PC->WasInputKeyJustPressed(EKeys::Escape)) {
    CloseDeckPanel(TEXT("esc"));
    return true;
  }
  if (PC->WasInputKeyJustPressed(EKeys::K)) {
    const bool bShift = PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift);
    ToggleDeckPanel(bShift ? ES09DeckSide::Opponent : ES09DeckSide::Own, TEXT("key"));
    return true;
  }
  return false;
}

void AS08FlowGameMode::SyncDeckLists() {
  if (bBenchDeckPanel) return;  // the bench owns its lists (BenchDeckPanelBegin)
  const int32 Revision = Flow.IsValid() ? Flow->GetDeckListsRevision() : -1;
  if (Revision == DeckListsRevision) return;
  DeckListsRevision = Revision;
  DeckLists.Reset();
  if (!Flow.IsValid()) return;
  const TSharedPtr<FJsonObject> Data = Flow->GetDeckListsData();
  if (!Data.IsValid()) return;
  FString Error;
  if (!S09DeckPanel::ParseDeckLists(Data, DeckLists, Error)) {
    DeckLists.Reset();
    FS08Trace::Write(TEXT("DECKLIST parse failed: ") + Error);
  }
}

void AS08FlowGameMode::RefreshDeckPanel() {
  const int64 Now = NowMs();
  // the auto-close: a new event asks me for input (my turn, my defense, my choice, my discard, game over)
  const FString Demand = DeckDemandKeyNow();
  const FS09DeckPanelView Before = DeckPanel;
  if (DeckPanel.NoteDemand(Demand, Now)) {
    FS08Trace::Write(FString::Printf(TEXT("DECK panel close side=%s t=%lld fade=%d why=input:%s"),
                                     S09DeckPanel::SideName(Before.Side()), static_cast<long long>(Now),
                                     FS09DeckPanelView::CloseMs, *S09DeckPanel::DemandKind(Demand)));
  }
  // prefetch: the list is static for the match - one request, before the first open
  if (Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && !bBenchDeckPanel) Flow->EnsureDeckLists();
  SyncDeckLists();
  if (!DeckPanelBox.IsValid() || !DeckPanel.IsVisible(Now)) return;
  RebuildDeckPanelContent();
}

void AS08FlowGameMode::RebuildDeckPanelContent() {
  const ES09DeckSide Side = DeckPanel.Side();
  const FS09PlayerPanel* Panel = Side == ES09DeckSide::Own ? Hud.ViewerPanel() : Hud.OpponentPanel();
  const FLinearColor Light = DeckSrgb(0xE6, 0xE8, 0xEE);
  const FLinearColor Muted = DeckSrgb(0x9A, 0xA0, 0xB0);
  const FLinearColor Gold = DeckSrgb(0xF2, 0xC1, 0x4E);
  TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);

  // header: whose deck, the side tabs, close
  const FString Hero = Panel ? PlayerHeroName(Panel->PlayerId) : FString();
  const FString Title = FString::Printf(TEXT("%s%s%s"), Side == ES09DeckSide::Own ? TEXT("YOUR DECK") : TEXT("OPPONENT DECK"),
                                        Hero.IsEmpty() ? TEXT("") : TEXT("  ·  "), *Hero);
  auto Tab = [this](ES09DeckSide TabSide, const TCHAR* Label, const TCHAR* Id) -> TSharedRef<SWidget> {
    const bool bActive = DeckPanel.IsOpen() && DeckPanel.Side() == TabSide;
    const float G = bActive ? 0.38f : 0.20f;
    return MakeHudPress(FName(Id), nullptr, [this, TabSide]() { ToggleDeckPanel(TabSide, TEXT("tab")); },
                        FMargin(8, 3), FLinearColor(G, G, G, 1.0f),
                        SNew(STextBlock).Text(FText::FromString(Label)).Font(FCoreStyle::GetDefaultFontStyle("Bold", 11)));
  };
  Box->AddSlot().AutoHeight()
      [SNew(SHorizontalBox) +
       SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
           [SNew(STextBlock).Text(FText::FromString(Title)).Font(DeckCardFont(18)).ColorAndOpacity(FSlateColor(Gold))] +
       SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
           [MakeHudPress(FName(TEXT("hud.deck.close")), nullptr, [this]() { CloseDeckPanel(TEXT("button")); },
                         FMargin(8, 3), FLinearColor(0.20f, 0.20f, 0.20f, 1.0f),
                         SNew(STextBlock).Text(FText::FromString(TEXT("CLOSE (Esc)")))
                             .Font(FCoreStyle::GetDefaultFontStyle("Bold", 11)))]];
  Box->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
      [SNew(SHorizontalBox) +
       SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 6, 0)[Tab(ES09DeckSide::Own, TEXT("YOURS (K)"), TEXT("hud.deck.tab.own"))] +
       SHorizontalBox::Slot().AutoWidth()[Tab(ES09DeckSide::Opponent, TEXT("OPPONENT (Shift+K)"), TEXT("hud.deck.tab.opp"))]];

  if (!Panel) {
    Box->AddSlot().AutoHeight().Padding(0, 10, 0, 0)
        [SNew(STextBlock).Text(FText::FromString(TEXT("no player data yet"))).Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
             .ColorAndOpacity(FSlateColor(Muted))];
    DeckPanelBox->SetContent(Box);
    return;
  }
  const FS09DeckPanelModel Model =
      FS09DeckPanelModel::Build(Side, *Panel, S09DeckPanel::FindList(DeckLists, Panel->PlayerId));
  const FString TraceLine = Model.TraceLine();
  if (TraceLine != DeckModelTraced) {
    FS08Trace::Write(TraceLine);
    DeckModelTraced = TraceLine;
  }

  // the counters (the server's numbers; "~" = counted at an older seq)
  const FString Stale = Model.bDeckStale ? TEXT("~") : TEXT("");
  FString Counters = FString::Printf(TEXT("IN DECK %s%d   ·   DISCARD %s%d"), *Stale, Model.DeckCount,
                                     Model.bDiscardStale ? TEXT("~") : TEXT(""), Model.DiscardCount);
  if (Side == ES09DeckSide::Own) {
    Counters += FString::Printf(TEXT("   ·   HAND %d"), Model.HandCount);
    if (Model.OutOfPlay > 0) Counters += FString::Printf(TEXT("   ·   OUT OF PLAY %d"), Model.OutOfPlay);
  }
  Box->AddSlot().AutoHeight().Padding(0, 8, 0, 0)
      [SNew(STextBlock).Text(FText::FromString(Counters)).Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
           .ColorAndOpacity(FSlateColor(Light))];
  if (Side == ES09DeckSide::Opponent) {
    // his hand: card backs by number - never a face, never a mark on the deck rows (SD-41 p. 4)
    TSharedRef<SWrapBox> Backs = SNew(SWrapBox).UseAllottedSize(true);
    for (int32 I = 0; I < Model.HandCount; ++I) {
      Backs->AddSlot().Padding(0, 0, 3, 3)
          [SNew(SBox).WidthOverride(14.0f).HeightOverride(20.0f)
               [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                    .BorderBackgroundColor(FSlateColor(DeckSrgb(0x6A, 0x2A, 0x30)))
                    .Padding(2.0f)[SNew(SColorBlock).Color(DeckSrgb(0x2A, 0x10, 0x14))]]];
    }
    Box->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 8, 0)
             [SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("HAND %d"), Model.HandCount)))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12)).ColorAndOpacity(FSlateColor(Light))] +
         SHorizontalBox::Slot().FillWidth(1.0f)[Backs]];
  }
  if (Model.HiddenDiscard > 0) {
    Box->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("%d face-down in the discard (combat, before the reveal)"),
                                                                 Model.HiddenDiscard)))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 11)).ColorAndOpacity(FSlateColor(Muted))];
  }
  Box->AddSlot().AutoHeight().Padding(0, 4, 0, 6)
      [SNew(STextBlock)
           .Text(FText::FromString(Side == ES09DeckSide::Own
                                       ? TEXT("whole deck, no draw order - copies side by side")
                                       : TEXT("whole deck, no draw order - his hand and deck look the same")))
           .Font(FCoreStyle::GetDefaultFontStyle("Regular", 11)).ColorAndOpacity(FSlateColor(Muted))];

  if (!Model.bListKnown) {
    const FS08FlowController::EDeckListsState State =
        Flow.IsValid() ? Flow->GetDeckListsState() : FS08FlowController::EDeckListsState::None;
    const TCHAR* Line = State == FS08FlowController::EDeckListsState::Failed
                            ? TEXT("deck list unavailable - counts only (reopen to retry)")
                            : TEXT("loading the deck list...");
    Box->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(STextBlock).Text(FText::FromString(Line)).Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
             .ColorAndOpacity(FSlateColor(Muted))];
    DeckPanelBox->SetContent(Box);
    return;
  }

  TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
  for (const FS09DeckRow& Row : Model.Rows) {
    const FString CardId = Row.Card.CardId;
    const bool bSelected = DeckPanelSelected == CardId;
    const bool bAllOut = Side == ES09DeckSide::Own && Row.Left == 0;  // every copy is in hand or discard
    TSharedRef<SHorizontalBox> Marks = SNew(SHorizontalBox);
    if (Row.InHand > 0) {
      Marks->AddSlot().AutoWidth().Padding(3, 0, 0, 0)
          [MarkChip(FString::Printf(TEXT("IN HAND %d"), Row.InHand), DeckSrgb(0x2E, 0x6B, 0x3A), Light)];
    }
    if (Row.InDiscard > 0) {
      Marks->AddSlot().AutoWidth().Padding(3, 0, 0, 0)
          [MarkChip(FString::Printf(TEXT("DISCARD %d"), Row.InDiscard), DeckSrgb(0x5A, 0x30, 0x30), Light)];
    }
    if (Row.Left >= 0) {
      Marks->AddSlot().AutoWidth().Padding(3, 0, 0, 0)
          [MarkChip(FString::Printf(TEXT("LEFT %d"), Row.Left), DeckSrgb(0x30, 0x36, 0x48), bAllOut ? Muted : Light)];
    }
    const FString Banner = Row.Card.BannerName.IsEmpty() || Row.Card.BannerName == TEXT("Any")
                               ? FString()
                               : FString::Printf(TEXT("  (%s)"), *Row.Card.BannerName);
    TSharedRef<SVerticalBox> Body = SNew(SVerticalBox);
    Body->AddSlot().AutoHeight()
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 6, 0)
             [SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("x%d"), Row.Card.Count)))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 13)).ColorAndOpacity(FSlateColor(Gold))] +
         SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
             [SNew(STextBlock).Text(FText::FromString(Row.Card.Name + Banner))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
                  .ColorAndOpacity(FSlateColor(bAllOut ? Muted : Light))] +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4, 0, 0, 0)
             [SNew(STextBlock).Text(FText::FromString(ValuesText(Row.Card)))
                  .Font(FCoreStyle::GetDefaultFontStyle("Regular", 11)).ColorAndOpacity(FSlateColor(Muted))]];
    Body->AddSlot().AutoHeight().Padding(0, 2, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
             [SNew(STextBlock).Text(FText::FromString(Row.Card.CardType))
                  .Font(FCoreStyle::GetDefaultFontStyle("Regular", 10)).ColorAndOpacity(FSlateColor(Muted))] +
         SHorizontalBox::Slot().AutoWidth()[Marks]];
    if (bSelected && !Row.Card.Text.IsEmpty()) {
      Body->AddSlot().AutoHeight().Padding(0, 4, 0, 0)
          [SNew(STextBlock).Text(FText::FromString(Row.Card.Text)).AutoWrapText(true)
               .Font(FCoreStyle::GetDefaultFontStyle("Regular", 11)).ColorAndOpacity(FSlateColor(Light))];
    }
    const float G = bSelected ? 0.24f : 0.13f;
    Rows->AddSlot().AutoHeight().Padding(0, 0, 0, 3)
        [MakeHudPress(
            FName(*FString::Printf(TEXT("hud.deck.row.%s"), *CardId)), nullptr,
            [this, CardId]() {
              DeckPanelSelected = DeckPanelSelected == CardId ? FString() : CardId;  // read-only: shows the text
              RefreshHud();
            },
            FMargin(0), FLinearColor(G, G, G + 0.02f, 1.0f),
            SNew(SHorizontalBox) +
                SHorizontalBox::Slot().AutoWidth()
                    [SNew(SBox).WidthOverride(4.0f)[SNew(SColorBlock).Color(TypeTint(Row.Card.CardType))]] +
                SHorizontalBox::Slot().FillWidth(1.0f).Padding(FMargin(8, 4))[Body])];
  }
  if (Model.Unlisted > 0) {
    Rows->AddSlot().AutoHeight().Padding(0, 4, 0, 0)
        [SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("%d card(s) outside the deck list"), Model.Unlisted)))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 11)).ColorAndOpacity(FSlateColor(Muted))];
  }
  Box->AddSlot().FillHeight(1.0f)[SNew(SScrollBox) + SScrollBox::Slot()[Rows]];
  DeckPanelBox->SetContent(Box);
}

void AS08FlowGameMode::TickDeckPanel() {
  if (!DeckPanelBorder.IsValid()) return;
  const int64 Now = NowMs();
  const float Alpha = DeckPanel.Opacity(Now);
  // clicks only while open; the close fade lets them through to the field
  const EVisibility Vis = Alpha <= 0.0f ? EVisibility::Collapsed
                          : DeckPanel.IsOpen() ? EVisibility::Visible
                                               : EVisibility::HitTestInvisible;
  if (DeckPanelBorder->GetVisibility() != Vis) {
    const bool bAppears = DeckPanelBorder->GetVisibility() == EVisibility::Collapsed && Vis != EVisibility::Collapsed;
    DeckPanelBorder->SetVisibility(Vis);
    if (bAppears) RebuildDeckPanelContent();
  }
  DeckPanelBorder->SetRenderOpacity(Alpha);
  // the side counters under it fade out with the open panel and take no clicks meanwhile (their right edge is shared,
  // a longer counter line would otherwise peek out); a panel the result screen collapsed stays collapsed
  if (const TSharedPtr<SWidget> Side = ArtHud.SidePanel.Pin()) {
    Side->SetRenderOpacity(1.0f - Alpha);
    const EVisibility Current = Side->GetVisibility();
    if (Current != EVisibility::Collapsed) {
      const EVisibility Want = Alpha > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Visible;
      if (Current != Want) Side->SetVisibility(Want);
    }
  }
}

bool AS08FlowGameMode::BenchDeckPanelBegin(const FS08Snapshot& Fixture, const FString& SideName, const FString& ListsPath) {
  FString Text;
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FFileHelper::LoadFileToString(Text, *ListsPath) || !FS08Contracts::TryParseJsonValue(Text, Value, Problem) ||
      !Value.IsValid() || !Value->AsObject().IsValid()) {
    FS08Trace::Write(FString::Printf(TEXT("BENCH deck-panel lists not loaded: %s"), *ListsPath));
    return false;
  }
  // the file is a GraphQL answer ({"data": {...}}) or its data object
  TSharedPtr<FJsonObject> Data = Value->AsObject();
  const TSharedPtr<FJsonObject>* Inner = nullptr;
  if (Data->TryGetObjectField(TEXT("data"), Inner) && Inner && Inner->IsValid()) Data = *Inner;
  FString Error;
  if (!S09DeckPanel::ParseDeckLists(Data, DeckLists, Error)) {
    FS08Trace::Write(TEXT("BENCH deck-panel lists parse failed: ") + Error);
    return false;
  }
  bBenchDeckPanel = true;
  // the HUD model of the fixture (hands, discard piles, deck counts) - the same model the live client builds
  Hud.Build(Fixture, BenchViewerId, TSet<FString>(), Fixture.SequenceNumber, Fixture.SequenceNumber);
  const ES09DeckSide Side = SideName.Equals(TEXT("opp"), ESearchCase::IgnoreCase) ? ES09DeckSide::Opponent : ES09DeckSide::Own;
  // at rest: fully open; the fixture's demand (my turn) is the one at the open, so it does not close the panel
  DeckPanel.Open(Side, NowMs() - FS09DeckPanelView::OpenMs, DeckDemandKeyNow());
  RefreshHud();
  TickDeckPanel();
  FS08Trace::Write(FString::Printf(TEXT("BENCH deck-panel side=%s lists=%d valid=%d"), S09DeckPanel::SideName(Side),
                                   DeckLists.Num(), Hud.bValid ? 1 : 0));
  return true;
}

void AS08FlowGameMode::TakeS09DeckPanelShots() {
  // Run F G-LIVE (DE-031): the deck panel of a live match. The auto client opens it in the opponent's turn (no input of
  // mine pending) once both public discard piles hold a card and the lists are loaded, frames my deck, switches to the
  // opponent's deck, frames it and leaves the panel open: my next turn (or my defense window) closes it by itself.
  // An early close before a frame retries on a later opponent turn (at most four attempts).
  if (!bAutoS09 || S09ShotDir.IsEmpty() || S09DeckShotStage >= 4 || !Flow.IsValid()) return;
  if (FScreenshotRequest::IsScreenshotRequested()) return;
  auto Interrupted = [this](const TCHAR* Why) {
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO deck-panel shots interrupted stage=%d why=%s try=%d"),
                                     S09DeckShotStage, Why, S09DeckShotTries));
    S09DeckShotStage = S09DeckShotTries >= 4 ? 4 : 0;
  };
  switch (S09DeckShotStage) {
    case 0: {
      const FS09PlayerPanel* Own = Hud.ViewerPanel();
      const FS09PlayerPanel* Opp = Hud.OpponentPanel();
      if (!Hud.bValid || Hud.bGameOver || Hud.bViewerTurn || !Own || !Opp || Own->Discard.Num() == 0 ||
          Opp->Discard.Num() == 0 || DeckLists.Num() < 2 || DeckPanel.IsOpen() || !DeckDemandKeyNow().IsEmpty()) {
        return;
      }
      ++S09DeckShotTries;
      const ES09DeckSide Side = bS09ShotDeckOwn ? ES09DeckSide::Opponent : ES09DeckSide::Own;
      FS08Trace::Write(FString::Printf(TEXT("S09AUTO deck-panel open side=%s try=%d discard=%d/%d"),
                                       S09DeckPanel::SideName(Side), S09DeckShotTries, Own->Discard.Num(),
                                       Opp->Discard.Num()));
      ToggleDeckPanel(Side, TEXT("auto"));
      S09DeckShotAt = Elapsed + 0.6f;  // open fade 80 ms + the rows' first paint
      S09DeckShotStage = bS09ShotDeckOwn ? 3 : 1;
      return;
    }
    case 1:
    case 3: {
      if (!DeckPanel.IsOpen()) {
        Interrupted(TEXT("closed"));
        return;
      }
      if (Elapsed < S09DeckShotAt) return;
      const bool bOwnShot = S09DeckShotStage == 1;
      (bOwnShot ? bS09ShotDeckOwn : bS09ShotDeckOpp) = true;
      const TCHAR* Leaf = bOwnShot ? TEXT("s09-deck-own.png") : TEXT("s09-deck-opp.png");
      FS08Trace::Write(FString::Printf(TEXT("S09AUTO run-f shot %s"), Leaf));
      TakeEvidenceShot(S09ShotDir / Leaf);
      S09DeckShotStage = bOwnShot ? 2 : 4;
      S09DeckShotAt = Elapsed + 0.3f;
      return;
    }
    case 2: {
      // the own frame is written (no request pending above): switch the open panel to the opponent's deck
      if (!DeckPanel.IsOpen()) {
        Interrupted(TEXT("closed"));
        return;
      }
      if (Elapsed < S09DeckShotAt) return;
      ToggleDeckPanel(ES09DeckSide::Opponent, TEXT("auto"));
      S09DeckShotAt = Elapsed + 0.6f;
      S09DeckShotStage = 3;
      return;
    }
    default:
      return;
  }
}

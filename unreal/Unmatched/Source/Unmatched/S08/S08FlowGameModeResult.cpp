// DE-029 (W-17; 01 F-06, D-DE-06, D-DE-09; 02 SD-24, SD-39, SD-45; 02-ux-ui-spec §2.9 UI-SCR-GAMEOVER): the result
// screen of the game mode - the part without GD-040 (IMPL p. 4: the FINISHED path; ABORTED and "Play again" wait).
//   - A full-screen modal over the frozen scene: the dim layer and a centred panel - the outcome, the headline by the
//     WINNING HERO (never by the fighter that struck the last blow), the reason, "Turn N · m:ss" from real fields, two
//     sides (left the winner's avatar disc, right the loser's as a dark silhouette), "VIEW BOARD" and "RETURN TO LOBBY".
//     The avatar is the team-colour disc with the hero monogram of the DE-023 portraits: the real Hero.avatarUrl is
//     HI-05 (the DB holds WebP, which the engine's image wrapper does not decode) - recorded in the run F journal.
//   - Opens when the DE-019 gate opens (hero gone + 1000 ms), fades in over 500 ms, never closes by itself.
//   - "View board" <-> "View results": a 250 ms crossfade of the modal against the board bar; on the board the turn
//     portraits come back (the fallen hero's heart), the gameplay panels stay collapsed, input stays dead (GD-036).
//   - The GD-036 pixel-gate markers (#FFD700 / #FF0064 / #00FFA0 / #8000FF, one per required element) are the thin
//     stripe at the top of the panel: tools/s09/run-duel-demo.ps1 and tools/s10/run-vs-ai-demo.ps1 keep gating them.
// Trace: 'RESULT summary ...' (once per distinct summary) and 'RESULT view ...' (S09/S09ResultScreen.h).
#include "S08FlowGameMode.h"

#include "S08ArtHudStyle.h"
#include "S08BoardActor.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "../S09/S09TurnHud.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace {
// The GD-036 markers (the same bytes as GS09Result*Marker in S08FlowGameMode.cpp - the pixel gates match them exactly).
constexpr FLinearColor GResultScreenMarker(FColor(255, 215, 0, 255));   // #FFD700
constexpr FLinearColor GResultOutcomeMarker(FColor(255, 0, 100, 255));  // #FF0064
constexpr FLinearColor GResultSupportMarker(FColor(0, 255, 160, 255));  // #00FFA0
constexpr FLinearColor GResultButtonMarker(FColor(128, 0, 255, 255));   // #8000FF
/** One stripe segment: 120 x 12 su = 80 x 8 px at 720p. The GD-036 gates (run-duel-demo, run-vs-ai-demo) sample every
 *  second pixel in both axes and want >= 100 samples of each marker: 40 x 4 = 160 at 720p. The first cut (120 x 6 su)
 *  gave 40 x 2 = 80 and failed the live duel gate at 720p (DE-031). */
constexpr float GMarkerW = 120.0f;
constexpr float GMarkerH = 12.0f;
constexpr float GPanelWidthSu = 760.0f;
constexpr float GDiscOuterSu = 120.0f;
constexpr float GDiscInnerSu = 108.0f;
/** The dim over the frozen scene (02 §2.9 "полноэкранная модаль поверх замороженной сцены"). */
constexpr float GDimAlpha = 0.72f;

FLinearColor Srgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}

/** A round disc of the given side (white - SImage tints it); the radius is half the side. */
const FSlateBrush* DiscBrush(bool bOuter) {
  static const FSlateRoundedBoxBrush Outer(FLinearColor::White, GDiscOuterSu * 0.5f, FVector2f(GDiscOuterSu, GDiscOuterSu));
  static const FSlateRoundedBoxBrush Inner(FLinearColor::White, GDiscInnerSu * 0.5f, FVector2f(GDiscInnerSu, GDiscInnerSu));
  return bOuter ? &Outer : &Inner;
}

FSlateFontInfo CardFont(int32 Size) { return FS08ArtHudFontToken(S08ArtHudFonts::CardTypeface, Size).Resolve(); }

TSharedRef<SWidget> MarkerStripe() {
  TSharedRef<SHorizontalBox> Row = SNew(SHorizontalBox);
  for (const FLinearColor& Color : {GResultScreenMarker, GResultOutcomeMarker, GResultSupportMarker, GResultButtonMarker}) {
    Row->AddSlot().AutoWidth()[SNew(SBox).WidthOverride(GMarkerW).HeightOverride(GMarkerH)[SNew(SColorBlock).Color(Color)]];
  }
  return Row;
}
}  // namespace

void AS08FlowGameMode::BuildResultScreenWidgets(const TSharedRef<SConstraintCanvas>& Canvas) {
  // over every HUD panel (added last): the dim and the centred panel; the content comes with RefreshHud
  Canvas->AddSlot()
      .Anchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f))
      .Offset(FMargin(0.0f))
      [SAssignNew(ResultOverlay, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(FLinearColor(0.0f, 0.0f, 0.0f, GDimAlpha)))
           .Padding(0.0f)
           .HAlign(HAlign_Center)
           .VAlign(VAlign_Center)
           .Visibility(EVisibility::Collapsed)
           [SAssignNew(ResultPanelBox, SBox)]];
  // the board view: a bar at the bottom centre - back to the results, or the lobby
  TSharedPtr<SBox> BarBox;
  Canvas->AddSlot()
      .Anchors(FAnchors(0.5f, 1.0f))
      .Alignment(FVector2D(0.5f, 1.0f))
      .Offset(FVector2D(0.0f, -32.0f))
      .AutoSize(true)
      [SAssignNew(ResultBoardBar, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(Srgb(0x16, 0x1A, 0x28, 0.92f)))
           .Padding(FMargin(16.0f, 10.0f))
           .Visibility(EVisibility::Collapsed)];
}

void AS08FlowGameMode::RebuildResultScreen() {
  if (ResultPanelBuiltAtElapsed < 0.0f) ResultPanelBuiltAtElapsed = Elapsed;  // settle clock for the capture
  const FS08RoomState Room = Flow.IsValid() && !bBenchResult ? Flow->GetRoom() : FS08RoomState();
  const FS08Snapshot Snap = bBenchResult ? BenchResultSnapshot
                            : Flow.IsValid() ? Flow->GetAppliedSnapshot()
                                             : FS08Snapshot();
  ResultSummary = FS09ResultSummary::Build(Hud, Snap, Room.StartedAt, Room.EndedAt);
  const FString Line = ResultSummary.TraceLine();
  if (Line != ResultSummaryTraced) {
    FS08Trace::Write(Line);
    ResultSummaryTraced = Line;
  }
  // the gameplay panels have no content on GAME_OVER - the board view shows the field and the portraits only
  for (const TWeakPtr<SWidget>& Panel : {ArtHud.CommandPanel, ArtHud.SidePanel, ArtHud.HandPanel}) {
    if (const TSharedPtr<SWidget> Widget = Panel.Pin()) Widget->SetVisibility(EVisibility::Collapsed);
  }
  if (!ResultPanelBox.IsValid() || !ResultBoardBar.IsValid()) return;

  const FString ViewerId = ViewerIdNow();
  const FS08ArtHudPlateStyle Chips;
  const FLinearColor Gold = Srgb(0xF2, 0xC1, 0x4E);
  const FLinearColor Light = Srgb(0xE6, 0xE8, 0xEE);
  const FLinearColor Muted = Srgb(0x9A, 0xA0, 0xB0);
  // the team colour of a side: the look of its hero (S08TeamLook, as the DE-023 portraits); viewer P1 without a figure
  auto TeamColor = [&](const FS09ResultSide& Side) {
    int32 Chip = Side.PlayerId == ViewerId ? 0 : 1;
    if (BoardActor) {
      for (const FS08BoardFighter& F : HudFighters()) {
        if (F.OwnerId != Side.PlayerId || !F.bIsHero) continue;
        const ES08TeamSlot Look = S08TeamLook(BoardActor->TeamOfFighter(F), F.OwnerId == ViewerId,
                                              static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode));
        Chip = Look == ES08TeamSlot::P1 ? 0 : 1;
        break;
      }
    }
    return Chips.TeamChipColor(static_cast<uint8>(Chip));
  };
  auto SideCard = [&](const FS09ResultSide& Side) -> TSharedRef<SWidget> {
    if (!Side.IsKnown()) return SNew(SBox).WidthOverride(260.0f);
    const FLinearColor Team = TeamColor(Side);
    // SD-45 p. 2: the winner on a disc of the team colour, the loser the same avatar dark to a silhouette on red
    const FLinearColor Outer = Side.bSilhouette ? Srgb(0x5A, 0x12, 0x14) : Team;
    const FLinearColor Inner = Side.bSilhouette ? Srgb(0x08, 0x08, 0x0A) : Team * 0.85f + FLinearColor(0, 0, 0, 0.15f);
    const FLinearColor MonoColor = Side.bSilhouette ? Srgb(0x22, 0x22, 0x28) : Srgb(0x16, 0x1A, 0x28);
    const FString Name = Side.HeroName.IsEmpty() ? (Side.bViewer ? FString(TEXT("You")) : FString(TEXT("Opponent")))
                                                 : Side.HeroName;
    const FString Tag = Side.bWinner ? TEXT("WINNER") : (Side.bSilhouette ? TEXT("DEFEATED") : TEXT(""));
    const FString Who = Side.bViewer ? TEXT("YOU") : TEXT("OPPONENT");
    const FString Hp = Side.bHpKnown ? FString::Printf(TEXT("HP %d / %d"), FMath::Max(0, Side.Hp), FMath::Max(0, Side.MaxHp))
                                     : FString(TEXT("HP -"));
    return SNew(SBox).WidthOverride(260.0f)
        [SNew(SVerticalBox) +
         SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
             [SNew(SBox).WidthOverride(GDiscOuterSu).HeightOverride(GDiscOuterSu)
                  [SNew(SOverlay) +
                   SOverlay::Slot()[SNew(SImage).Image(DiscBrush(true)).ColorAndOpacity(FSlateColor(Outer))] +
                   SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
                       [SNew(SBox).WidthOverride(GDiscInnerSu).HeightOverride(GDiscInnerSu)
                            [SNew(SImage).Image(DiscBrush(false)).ColorAndOpacity(FSlateColor(Inner))]] +
                   SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
                       [SNew(STextBlock)
                            .Text(FText::FromString(S09TurnHud::Monogram(Name)))
                            .Font(CardFont(44))
                            .ColorAndOpacity(FSlateColor(MonoColor))]]] +
         SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 10.0f, 0.0f, 0.0f)
             [SNew(STextBlock).Text(FText::FromString(Name)).Font(CardFont(22))
                  .ColorAndOpacity(FSlateColor(Side.bSilhouette ? Muted : Light))] +
         SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
             [SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("%s  ·  %s"), *Who, *Hp)))
                  .Font(FCoreStyle::GetDefaultFontStyle("Regular", 13))
                  .ColorAndOpacity(FSlateColor(Muted))] +
         SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 4.0f, 0.0f, 0.0f)
             [SNew(STextBlock).Text(FText::FromString(Tag)).Font(CardFont(16))
                  .ColorAndOpacity(FSlateColor(Side.bWinner ? Gold : Srgb(0xD0, 0x5A, 0x5A)))]];
  };

  const FLinearColor OutcomeTint = Hud.bWinnerKnown ? (Hud.bViewerWon ? Srgb(0x8C, 0xE6, 0x9A) : Srgb(0xF0, 0x8A, 0x8A))
                                                    : Srgb(0xC8, 0xCC, 0xD6);
  auto LobbyBlocked = [this]() { return bS09LobbyReturnSent ? FS09Reason::Make(TEXT("why.syncing")) : FS09Reason(); };
  const FString LobbyLabel = bS09LobbyReturnSent ? TEXT("RETURNING TO LOBBY...") : TEXT("RETURN TO LOBBY (Enter)");
  TSharedRef<SWidget> Panel =
      SNew(SBox).WidthOverride(GPanelWidthSu)
          [SNew(SBorder)
               .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
               .BorderBackgroundColor(FSlateColor(Srgb(0x0B, 0x0E, 0x18, 0.96f)))
               .Padding(FMargin(32.0f, 20.0f, 32.0f, 24.0f))
               [SNew(SVerticalBox) +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 0.0f, 0.0f, 14.0f)[MarkerStripe()] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                    [SNew(STextBlock).Text(FText::FromString(ResultSummary.Outcome)).Font(CardFont(48))
                         .ColorAndOpacity(FSlateColor(OutcomeTint))
                         .ShadowOffset(FVector2D(1.0f, 1.0f))
                         .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f))] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                    [SNew(STextBlock).Text(FText::FromString(ResultSummary.Headline)).Font(CardFont(28))
                         .ColorAndOpacity(FSlateColor(Gold))] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 6.0f, 0.0f, 0.0f)
                    [SNew(STextBlock).Text(FText::FromString(ResultSummary.ReasonText))
                         .Font(FCoreStyle::GetDefaultFontStyle("Regular", 16))
                         .ColorAndOpacity(FSlateColor(Light))] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 2.0f, 0.0f, 0.0f)
                    [SNew(STextBlock).Text(FText::FromString(ResultSummary.StatsLine()))
                         .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))
                         .ColorAndOpacity(FSlateColor(Muted))] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 18.0f, 0.0f, 0.0f)
                    [SNew(SHorizontalBox) +
                     SHorizontalBox::Slot().AutoWidth()[SideCard(ResultSummary.Left)] +
                     SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(16.0f, 0.0f, 16.0f, 40.0f)
                         [SNew(STextBlock).Text(FText::FromString(TEXT("VS"))).Font(CardFont(24))
                              .ColorAndOpacity(FSlateColor(Muted))] +
                     SHorizontalBox::Slot().AutoWidth()[SideCard(ResultSummary.Right)]] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 20.0f, 0.0f, 0.0f)
                    [SNew(SHorizontalBox) +
                     SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 12.0f, 0.0f)
                         [MakeHudPress(
                              FName(TEXT("hud.result.board")), nullptr,
                              [this]() { ToggleResultBoard(TEXT("button")); }, FMargin(16, 8), FLinearColor::White,
                              SNew(STextBlock).Text(FText::FromString(TEXT("VIEW BOARD (V)"))).Font(CardFont(18)))] +
                     SHorizontalBox::Slot().AutoWidth()
                         [MakeHudPress(FName(TEXT("hud.result.lobby")), LobbyBlocked, [this]() { ReturnToLobbyCommand(); },
                                       FMargin(16, 8), FLinearColor::White,
                                       SNew(STextBlock).Text(FText::FromString(LobbyLabel)).Font(CardFont(18)))]] +
                SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 10.0f, 0.0f, 0.0f)
                    [SNew(STextBlock)
                         .Text(FText::FromString(TEXT("Enter / Esc / L - lobby    V - view the board    gameplay input is over")))
                         .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
                         .ColorAndOpacity(FSlateColor(Muted))]]];
  ResultPanelBox->SetContent(Panel);

  ResultBoardBar->SetContent(
      SNew(SHorizontalBox) +
      SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 16.0f, 0.0f)
          [SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("FINAL BOARD  ·  %s"), *ResultSummary.Outcome)))
               .Font(CardFont(18))
               .ColorAndOpacity(FSlateColor(Gold))] +
      SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 12.0f, 0.0f)
          [MakeHudPress(FName(TEXT("hud.result.back")), nullptr, [this]() { ToggleResultBoard(TEXT("button")); },
                        FMargin(14, 6), FLinearColor::White,
                        SNew(STextBlock).Text(FText::FromString(TEXT("VIEW RESULTS (Esc)"))).Font(CardFont(16)))] +
      SHorizontalBox::Slot().AutoWidth()
          [MakeHudPress(FName(TEXT("hud.result.board.lobby")), LobbyBlocked, [this]() { ReturnToLobbyCommand(); },
                        FMargin(14, 6), FLinearColor::White,
                        SNew(STextBlock).Text(FText::FromString(bS09LobbyReturnSent ? TEXT("RETURNING TO LOBBY...")
                                                                                     : TEXT("RETURN TO LOBBY (L)")))
                            .Font(CardFont(16)))]);
}

void AS08FlowGameMode::TickResultScreen() {
  const int64 Now = NowMs();
  const bool bShown = IsResultScreenShown();
  if (bShown && !ResultView.IsOpen()) {
    ResultView.Open(Now);
    FS08Trace::Write(FString::Printf(TEXT("RESULT view mode=results t=%lld intro=%d fade=0 why=open"),
                                     static_cast<long long>(Now), FS09ResultView::IntroMs));
  } else if (!bShown && ResultView.IsOpen()) {
    ResultView.Reset();
  }
  if (ResultOverlay.IsValid()) {
    const float Alpha = ResultView.ResultsAlpha(Now);
    const EVisibility Vis = Alpha <= 0.0f ? EVisibility::Collapsed
                            : ResultView.ResultsHitTestable() ? EVisibility::Visible
                                                              : EVisibility::HitTestInvisible;
    if (ResultOverlay->GetVisibility() != Vis) ResultOverlay->SetVisibility(Vis);
    ResultOverlay->SetRenderOpacity(Alpha);
  }
  const float BarAlpha = ResultView.BoardBarAlpha(Now);
  if (ResultBoardBar.IsValid()) {
    const EVisibility Vis = BarAlpha <= 0.0f ? EVisibility::Collapsed
                            : ResultView.IsBoardView() ? EVisibility::Visible
                                                       : EVisibility::HitTestInvisible;
    if (ResultBoardBar->GetVisibility() != Vis) ResultBoardBar->SetVisibility(Vis);
    ResultBoardBar->SetRenderOpacity(BarAlpha);
  }
  // the turn portraits fade in with the board (the fallen hero's heart, SD-38); TickTurnHud shows them on the board
  if (TurnPortraitColumn.IsValid()) TurnPortraitColumn->SetRenderOpacity(ResultView.IsOpen() ? BarAlpha : 1.0f);
}

void AS08FlowGameMode::ToggleResultBoard(const TCHAR* Why) {
  const int64 Now = NowMs();
  if (!ResultView.ToggleBoard(Now)) return;
  FS08Trace::Write(FString::Printf(TEXT("RESULT view mode=%s t=%lld intro=0 fade=%d why=%s"),
                                   ResultView.IsBoardView() ? TEXT("board") : TEXT("results"),
                                   static_cast<long long>(Now), FS09ResultView::CrossfadeMs, Why));
  TickResultScreen();
}

void AS08FlowGameMode::BenchResultBegin(const FS08Snapshot& Fixture, bool bBoard, bool bViewerLoses) {
  // the terminal body exactly as the server writes it for a hero kill (applyTerminalState): GAME_OVER, winnerId, the
  // loser hero at HP 0 and the loser player not alive - everything else is the fixture
  FString OtherId;
  const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
  if (Fixture.Players.IsValid() && Fixture.Players->TryGetArray(List) && List) {
    for (const TSharedPtr<FJsonValue>& Value : *List) {
      const TSharedPtr<FJsonObject> P = Value.IsValid() ? Value->AsObject() : nullptr;
      if (P.IsValid() && P->GetStringField(TEXT("userId")) != BenchViewerId) OtherId = P->GetStringField(TEXT("userId"));
    }
  }
  const FString WinnerId = bViewerLoses ? OtherId : BenchViewerId;
  const FString LoserId = bViewerLoses ? BenchViewerId : OtherId;
  auto MapEntries = [](const TSharedPtr<FJsonValue>& Array, TFunctionRef<void(const TSharedRef<FJsonObject>&)> Edit) {
    const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
    if (!Array.IsValid() || !Array->TryGetArray(Entries) || !Entries) return Array;
    TArray<TSharedPtr<FJsonValue>> Out;
    for (const TSharedPtr<FJsonValue>& Value : *Entries) {
      const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
      if (!Object.IsValid()) continue;
      const TSharedRef<FJsonObject> Copy = MakeShared<FJsonObject>(*Object);
      Edit(Copy);
      Out.Add(MakeShared<FJsonValueObject>(Copy));
    }
    return TSharedPtr<FJsonValue>(MakeShared<FJsonValueArray>(Out));
  };
  FS08Snapshot S = Fixture;
  S.Phase = TEXT("GAME_OVER");
  const TSharedRef<FJsonObject> Meta = S.Metadata.IsValid() && S.Metadata->AsObject().IsValid()
                                           ? MakeShared<FJsonObject>(*S.Metadata->AsObject())
                                           : MakeShared<FJsonObject>();
  Meta->SetStringField(TEXT("winnerId"), WinnerId);
  S.Metadata = MakeShared<FJsonValueObject>(Meta);
  S.Fighters = MapEntries(S.Fighters, [&LoserId](const TSharedRef<FJsonObject>& F) {
    if (F->GetStringField(TEXT("ownerId")) == LoserId && F->GetStringField(TEXT("type")) == TEXT("HERO")) {
      F->SetNumberField(TEXT("health"), 0);
    }
  });
  S.Players = MapEntries(S.Players, [&LoserId](const TSharedRef<FJsonObject>& P) {
    if (P->GetStringField(TEXT("userId")) == LoserId) {
      P->SetBoolField(TEXT("isAlive"), false);
      P->SetNumberField(TEXT("health"), 0);
    }
  });
  BenchResultSnapshot = S;
  bBenchResult = true;
  // the fallen hero's figure is gone on the final board (DE-019 dissolved it before the screen)
  FS08BoardModel::DecodeFighters(S.Fighters, Fighters);
  SyncBoardFromApplied();
  Hud.Build(S, BenchViewerId, TSet<FString>(), S.SequenceNumber, S.SequenceNumber);
  FString GateLine;
  ResultGate.Update(NowMs(), S.SequenceNumber, Hud.bGameOver, false, -1, GateLine);
  if (!GateLine.IsEmpty()) FS08Trace::Write(GateLine);
  RefreshHud();
  TickResultScreen();
  if (bBoard) ToggleResultBoard(TEXT("bench"));
  FS08Trace::Write(FString::Printf(TEXT("BENCH result mode=%s viewerWins=%d valid=%d shown=%d"),
                                   bBoard ? TEXT("board") : TEXT("results"), bViewerLoses ? 0 : 1, Hud.bValid ? 1 : 0,
                                   IsResultScreenShown() ? 1 : 0));
}

bool AS08FlowGameMode::HandleResultKeys(APlayerController* PC) {
  if (!PC || !ResultView.IsOpen()) return false;
  TOptional<ES09ResultKey> Key;
  if (PC->WasInputKeyJustPressed(EKeys::Escape)) {
    Key = ES09ResultKey::Escape;
  } else if (PC->WasInputKeyJustPressed(EKeys::Enter)) {
    Key = ES09ResultKey::Enter;
  } else if (PC->WasInputKeyJustPressed(EKeys::L)) {
    Key = ES09ResultKey::L;
  } else if (PC->WasInputKeyJustPressed(EKeys::V)) {
    Key = ES09ResultKey::V;
  }
  if (!Key.IsSet()) return false;
  switch (ResultView.OnKey(Key.GetValue())) {
    case ES09ResultAction::Lobby:
      ReturnToLobbyCommand();
      return true;
    case ES09ResultAction::ToggleBoard:
      ToggleResultBoard(TEXT("key"));
      return true;
    default:
      return false;
  }
}

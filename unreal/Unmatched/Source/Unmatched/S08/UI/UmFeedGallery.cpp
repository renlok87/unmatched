// VS-4 HB-39...HB-41 review sheet - see UmFeedGallery.h.
#include "UmFeedGallery.h"

#include "../../S09/S09OpponentView.h"
#include "UmCardGallery.h"
#include "UmGameHud.h"
#include "UmHandGallery.h"
#include "UmHudFeed.h"
#include "UmHudHand.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace UmFeedGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("log"),          TEXT("toast-info"), TEXT("toast-warning"),
                                           TEXT("toast-error"),  TEXT("toast-stack"), TEXT("toast-bottom"),
                                           TEXT("sub"),          TEXT("sub-lowered"), TEXT("combat")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}
}  // namespace UmFeedGallery

namespace {
/** The figure polygons of the bench frames (HB-07 masks.json), as boxes + 4 px, in 1080p px. */
TArray<FBox2D> UmFgFigures1080(const FString& Board) {
  TArray<FBox2D> Out;
  const FString Path = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../art/imagegen/hud-composition-v1-codex/masks.json")));
  FString Text;
  TSharedPtr<FJsonObject> Root;
  if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) ||
      !Root.IsValid()) {
    return Out;
  }
  const TSharedPtr<FJsonObject>* Polys = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
  if (!Root->TryGetObjectField(TEXT("figure_polygons_1080p"), Polys) || !(*Polys)->TryGetArrayField(Board, List)) return Out;
  for (const TSharedPtr<FJsonValue>& P : *List) {
    FBox2D B(ForceInit);
    for (const TSharedPtr<FJsonValue>& Pt : P->AsArray()) {
      const TArray<TSharedPtr<FJsonValue>>& XY = Pt->AsArray();
      if (XY.Num() >= 2) B += FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber());
    }
    if (B.bIsValid) Out.Add(B.ExpandBy(4.0));
  }
  return Out;
}

FUmHandModel UmFgHand(const TArray<FS09CardView>& Deck, const FString& Hero, std::initializer_list<const TCHAR*> Names, bool bLowered) {
  FUmHandModel M;
  M.HandMaxSize = 7;
  M.HeroSlug = Hero;
  M.bLowered = bLowered;
  int32 Copy = 0;
  for (const TCHAR* Name : Names) {
    FUmHandCardModel Card;
    for (const FS09CardView& C : Deck) {
      if (C.Name == Name) Card.Card = C;
    }
    if (Card.Card.Name.IsEmpty()) Card.Card.Name = Name;
    Card.Card.InstanceId = FString::Printf(TEXT("card::%s-%d"), Name, Copy++);
    M.Cards.Add(Card);
  }
  return M;
}

FUmToastSpec UmFgSpec(EUmToastKind Kind, const TCHAR* Key, const FText& Text, bool bSticky = false) {
  FUmToastSpec S;
  S.Kind = Kind;
  S.Key = FName(Key);
  S.Text = Text;
  S.bSticky = bSticky;
  S.HoldSec = 4.0f;
  return S;
}
}  // namespace

bool UUmFeedGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

TArray<FString> UUmFeedGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    Lines.Add(TEXT("UMGALLERY feed canvas=0x0"));
    return Lines;
  }
  Root->ClearChildren();
  BoardNow = Board.ToLower();
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  const FBox2D Field = UmHandGallery::FieldSu(BoardNow, CanvasSu, PxPerSu);
  Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, &Field);
  const FString Rel = bSarpedon ? TEXT("docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png")
                                : TEXT("docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png");
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / Rel);
  // -S08IconGalleryHandPlain: no picture (a sheet for git - no board art, with -S08CardArtLegacy no scans either)
  BackgroundTexture = FParse::Param(FCommandLine::Get(), TEXT("S08IconGalleryHandPlain")) ? nullptr : FImageUtils::ImportFileAsTexture2D(Path);
  Background = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Background")));
  if (BackgroundTexture) {
    Background->SetBrushFromTexture(BackgroundTexture);
  } else {
    Background->SetColorAndOpacity(UUmHudTheme::Get().Color(TEXT("panel.bg.inset")));
  }
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Background)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
    S->SetOffsets(FMargin(0.0f));
  }
  // the figures of the frame: 1080p px -> su of this canvas (the frame stretches over the window)
  FiguresSu.Reset();
  for (const FBox2D& B : UmFgFigures1080(BoardNow)) {
    const FVector2D K(CanvasSu.X / 1920.0, CanvasSu.Y / 1080.0);
    FiguresSu.Add(FBox2D(B.Min * K, B.Max * K));
  }
  Medusa = UmCardGallery::LoadDeck(TEXT("medusa"));
  Arthur = UmCardGallery::LoadDeck(TEXT("king-arthur"));
  Hand = CreateWidget<UUmHudHand>(this, UUmHudHand::StaticClass());
  if (Hand) {
    Hand->SetSyncLoad(true);
    Hand->SetClockOverrideMs(0.0);
    const FUmHandFrame Frame = FUmHandFrame::FromLayout(Layout, 1.0f);
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Hand)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f));
      S->SetPosition(Frame.SlotSu.Min);
      S->SetSize(Frame.SlotSu.GetSize());
    }
    Hand->SetFrame(Frame);
  }
  Game = CreateWidget<UUmGameHud>(this, UUmGameHud::StaticClass());
  if (Game) {
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Game)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
      S->SetOffsets(FMargin(0.0f));
    }
    Feed = FUmFeedBlocks();
    Lines.Append(Feed.Build(*Game, S08ArtLook::FS08SlateHudBlocks(), nullptr, FUmFeedBlocks::FCallbacks()));
    Game->ApplyLayout(Layout, TArray<FName>(), false);
  }
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(CanvasSu.X - 560.0, Layout.MarginSu));
  }
  PushLog(0.0);
  StateNow = -1;
  Lines.Add(FString::Printf(TEXT("UMGALLERY feed board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s figures=%d medusa=%d arthur=%d"),
                            *BoardNow, CanvasSu.X, CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"), FiguresSu.Num(),
                            Medusa.Num(), Arthur.Num()));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

void UUmFeedGalleryWidget::PushLog(double NowMs) {
  // run I (HB-38 facts.logs): Marmoreal host (Medusa) up to MS-LOG seq 23, Sarpedon joiner (King Arthur) up to seq 26;
  // the cells by label, the players and fighters by the database names, the card names as the client has them
  // (Medusa RU from i18n.ru, King Arthur EN = Card.nameRu, ВР-VS2-HB38-14)
  struct FRow {
    int32 Seq;
    int32 Turn;
    int32 Team;  // 0 = Medusa (P1), 1 = King Arthur (P2)
    const TCHAR* Source;
    const TCHAR* Card;
    const TCHAR* Moves;  // "fighter:from:to;..." ('' = no movement)
  };
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  static const FRow Marmoreal[] = {{5, 1, 0, TEXT("MANEUVER"), TEXT(""), TEXT("Medusa:M13:M25")},
                                   {7, 2, 1, TEXT("MANEUVER"), TEXT(""), TEXT("King Arthur:M31:M26;Merlin:M23:M16")},
                                   {13, 3, 0, TEXT("MANEUVER"), TEXT(""), TEXT("")},
                                   {15, 3, 0, TEXT("MANEUVER"), TEXT(""), TEXT("")},
                                   {22, 3, 0, TEXT("EFFECT"), TEXT("Рывок"), TEXT("")},
                                   {23, 4, 1, TEXT("EFFECT"), TEXT("Skirmish"), TEXT("")}};
  static const FRow Sarpedon[] = {{3, 1, 0, TEXT("MANEUVER"), TEXT(""), TEXT("Medusa:S20:S35")},
                                  {5, 1, 0, TEXT("MANEUVER"), TEXT(""), TEXT("Medusa:S35:S36")},
                                  {9, 1, 0, TEXT("EFFECT"), TEXT("Рывок"), TEXT("")},
                                  {13, 2, 1, TEXT("EFFECT"), TEXT("Swift Strike"), TEXT("")},
                                  {24, 4, 1, TEXT("EFFECT"), TEXT("Noble Sacrifice"), TEXT("")},
                                  {26, 4, 1, TEXT("MANEUVER"), TEXT(""), TEXT("")}};
  for (const FRow& R : (bSarpedon ? TArrayView<const FRow>(Sarpedon) : TArrayView<const FRow>(Marmoreal))) {
    FS09LastMovement T;
    T.bValid = true;
    T.Seq = R.Seq;
    T.PlayerId = R.Team == 0 ? TEXT("p-medusa") : TEXT("p-arthur");
    T.Source = R.Source;
    TArray<FString> Labels;
    TArray<FString> Parts;
    FString(R.Moves).ParseIntoArray(Parts, TEXT(";"));
    for (const FString& Part : Parts) {
      TArray<FString> F;
      Part.ParseIntoArray(F, TEXT(":"));
      if (F.Num() != 3) continue;
      FS09LastMovement::FMove Move;
      Move.FighterId = F[0];
      Move.From = FIntPoint(Labels.Add(F[1]), 0);
      Move.Path = {FIntPoint(Labels.Add(F[2]), 0)};
      T.Moves.Add(Move);
    }
    FUmLogEntry E;
    E.Seq = R.Seq;
    E.Turn = R.Turn;
    E.TeamSlot = R.Team;
    UmHudLog::DescribeTrail(
        T, R.Card, {}, [](const FString& Id) { return Id == TEXT("p-medusa") ? FString(TEXT("Medusa")) : FString(TEXT("King Arthur")); },
        [](const FString& Id) { return Id; }, [&Labels](const FIntPoint& C) { return Labels.IsValidIndex(C.X) ? Labels[C.X] : FString(); },
        E.Text, E.Full);
    Feed.PushLog(E, NowMs);
  }
}

FUmFeedInput UUmFeedGalleryWidget::InputNow(double NowMs) const {
  FUmFeedInput In;
  In.Layout = &Layout;
  In.bLive = true;
  In.NowMs = NowMs;
  In.bCombat = bCombat;
  In.StatusBottomSu = static_cast<float>(Layout.Rect(EUmHudBlock::Status).Min.Y) + 48.0f;
  In.Figures = FiguresSu;
  In.Spaces.Add(Layout.FieldSu);
  for (const EUmHudBlock B : {EUmHudBlock::Top, EUmHudBlock::PanelLoc, EUmHudBlock::PanelOpp, EUmHudBlock::OppHand, EUmHudBlock::Decks,
                              EUmHudBlock::Actions}) {
    if (Layout.HasRect(B)) In.Blocks.Add(Layout.Rect(B));
  }
  // the status capsule (one line, 48 su) and the log column (class L, out of the combat)
  In.Blocks.Add(Layout.Rect(EUmHudBlock::Status));
  if (!Layout.bClassS && !bCombat) In.Blocks.Add(Layout.Rect(EUmHudBlock::Log));
  if (bCombat) {
    // the defense window on the defender's HUD (HB-29, the HB-38 combat overlay): both edges with the ribbons and the
    // defender's buttons; no centre there (the attacker's HUD has «Ждём защиту…» - the live client takes the drawn one)
    In.Blocks.Add(UmGameHudSlots::SlotRect(Layout, EUmGameSlot::CombatEdgeL));
    In.Blocks.Add(UmGameHudSlots::SlotRect(Layout, EUmGameSlot::CombatEdgeR));
  }
  if (Hand) {
    const UmHudHand::FRow& Row = Hand->GetRow();
    const float Lower = Hand->GetLowerNowSu();
    FBox2D Cards(ForceInit);
    for (const FVector2D& Pos : Row.CardPos) {
      Cards += FBox2D(FVector2D(Pos.X, Pos.Y + Lower), FVector2D(Pos.X + Row.CardSize.X, FMath::Min(Layout.CanvasSu.Y, Pos.Y + Lower + Row.CardSize.Y)));
    }
    if (Cards.bIsValid) {
      In.Blocks.Add(Cards);
      In.CardsTopSu = static_cast<float>(Cards.Min.Y);
    }
    if (Hand->IsCaptionShown()) In.CaptionSu = Hand->CaptionRectSu();
    In.bHandLowered = Lower > 0.5f;
  }
  return In;
}

void UUmFeedGalleryWidget::ApplyState(int32 State, double Start, TArray<FString>& Lines) {
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  UUmToastStack* Toasts = Feed.GetToasts();
  if (Toasts) Toasts->Clear();
  Feed.HideSubtitle();
  Feed.Invalidate();
  bCombat = State == 8;
  const bool bLowered = State == 5 || State == 7;
  if (Hand) {
    Hand->SetClockOverrideMs(Start - 1000.0);  // lowered already at the frame (LowerMs 150)
    if (bSarpedon) {
      Hand->ApplyModel(UmFgHand(Arthur, TEXT("king-arthur"), {TEXT("The Holy Grail"), TEXT("Noble Sacrifice"), TEXT("Swift Strike")}, bLowered));
    } else {
      Hand->ApplyModel(UmFgHand(Medusa, TEXT("medusa"),
                                {TEXT("Gaze of Stone"), TEXT("Gaze of Stone"), TEXT("Snipe"), TEXT("Clutching Claws"), TEXT("Dash")}, bLowered));
    }
    Hand->SetClockOverrideMs(Start);
    Hand->Step();
  }
  Feed.SetLogOpen(State == 0);
  auto Text = [](EUmTable T, const TCHAR* Key, int32 N = -1) {
    if (N < 0) return UmText::Get(T, Key);
    FFormatNamedArguments A;
    A.Add(TEXT("n"), FText::FromString(FString::FromInt(N)));
    return UmText::Format(T, Key, A);
  };
  const FUmToastSpec Info = UmFgSpec(EUmToastKind::Info, TEXT("hud.toast.reconnected"), Text(EUmTable::Hud, TEXT("hud.toast.reconnected"), 0));
  FUmSubtitleModel Long;
  Long.Speaker = UmHudSubtitle::SpeakerText(TEXT("King Arthur"));
  Long.Line = FText::FromString(TEXT("Оставь себе свой взгляд, горгона. Мне хватит меча."));  // ARTHUR-MATCHUP-MEDUSA-01 RU
  Long.StartMs = Start;
  Long.DurationMs = 5000.0;
  switch (State) {
    case 1:
      Feed.PushToast(Info, Start);
      break;
    case 2:
      Feed.PushToast(UmFgSpec(EUmToastKind::Warning, TEXT("ms.hint.hand.limit"), Text(EUmTable::Ms, TEXT("ms.hint.hand.limit"), 7), true), Start);
      break;
    case 3:
      Feed.PushToast(UmFgSpec(EUmToastKind::Error, TEXT("why.not.your.turn"), Text(EUmTable::Why, TEXT("why.not.your.turn"))), Start);
      break;
    case 4:
      Feed.PushToast(Info, Start);
      Feed.PushToast(UmFgSpec(EUmToastKind::Error, TEXT("why.client.desync"), Text(EUmTable::Why, TEXT("why.client.desync"))), Start);
      break;
    case 5:
      Feed.PushToast(UmFgSpec(EUmToastKind::Error, TEXT("why.not.in.range"), Text(EUmTable::Why, TEXT("why.not.in.range"))), Start);
      break;
    case 6:
      Feed.ShowSubtitle(Long);
      break;
    case 7: {
      FUmSubtitleModel Short = Long;
      Short.Line = FText::FromString(TEXT("Защищайся!"));  // ARTHUR-ATTACK-01 RU
      Feed.ShowSubtitle(Short);
      break;
    }
    case 8:
      Feed.PushToast(Info, Start);
      Feed.PushToast(UmFgSpec(EUmToastKind::Error, TEXT("why.client.desync"), Text(EUmTable::Why, TEXT("why.client.desync"))), Start);
      Feed.ShowSubtitle(Long);
      break;
    default:
      break;
  }
  bBadgeDone = !(State == 3 || State == 5);
  if (Label) {
    Label->SetText(FText::FromString(FString::Printf(TEXT("HB-39/40/41 sheet · %s · %s (review tooling, not an acceptance frame)"), *BoardNow,
                                                     UmFeedGallery::StateName(State))));
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY feed board=%s state=%d:%s"), *BoardNow, State, UmFeedGallery::StateName(State)));
}

TArray<FString> UUmFeedGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  if (!Game) return Lines;
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmFeedGallery::StateCount - 1);
  if (State != StateNow) {
    StateNow = State;
    StateStart = 1000.0 * State;
    ApplyState(State, StateStart, Lines);
    // the state starts at its second (the sheet's clock jumps to the shot times): the toasts appear, the log hides
    if (Hand) {
      Hand->SetClockOverrideMs(StateStart);
      Hand->Step();
    }
    Lines.Append(Feed.Refresh(InputNow(StateStart)));
  }
  if (Hand) {
    Hand->SetClockOverrideMs(TMs);
    Hand->Step();
  }
  // the refusal badge 400 ms into the state (it lives 350 ms: the shot at + 600 shows it)
  if (!bBadgeDone && TMs >= StateStart + 400.0) {
    bBadgeDone = true;
    FVector2D At = FVector2D::ZeroVector;
    if (State == 3) {
      // «Конец хода» - the last disc of ACTIONS: its top-right corner
      const FBox2D& A = Layout.Rect(EUmHudBlock::Actions);
      At = FVector2D(A.Max.X - 16.0, A.Min.Y + 4.0);
    } else {
      // the refused target's space (HB-38 facts.board_figures: Marmoreal King Arthur M31, Sarpedon Medusa S20)
      const int32 I = BoardNow == TEXT("sarpedon") ? 3 : 5;
      if (FiguresSu.IsValidIndex(I)) At = FVector2D(FiguresSu[I].GetCenter().X, FiguresSu[I].Max.Y);
    }
    Feed.ShowBadge(At, TMs);
  }
  Lines.Append(Feed.Refresh(InputNow(TMs)));
  Feed.CollectShotLines(Lines, Layout.PxPerSu);
  return Lines;
}

// VS-2 HB-10 / HB-11 review sheets - see UmHudGallery.h.
#include "UmHudGallery.h"

#include "../S08HudTokens.generated.h"
#include "UmButton.h"
#include "UmHudBanner.h"
#include "UmHudLayout.h"
#include "UmHudStatusLine.h"
#include "UmHudTop.h"
#include "UmHudOppHand.h"
#include "UmHudPlayerPanel.h"
#include "UmPortrait.h"
#include "../S08ArtHudStyle.h"
#include "../S08TurnPortraitWidget.h"
#include "Misc/CommandLine.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/GridPanel.h"
#include "Components/GridSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"

namespace {
UTextBlock* UmGalText(UWidgetTree& Tree, const FString& Text, FName ColorToken) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  T->SetText(FText::FromString(Text));
  T->SetFont(Theme.Font(TEXT("type.caption")));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(ColorToken)));
  T->SetShadowOffset(FVector2D::ZeroVector);
  return T;
}

void UmGalPut(UGridPanel* Grid, UWidget* W, int32 Row, int32 Col, const FMargin& Pad) {
  if (UGridSlot* Slot = Grid->AddChildToGrid(W, Row, Col)) {
    Slot->SetPadding(Pad);
    Slot->SetHorizontalAlignment(HAlign_Left);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
}

constexpr float UmGalRowSu = 72.0f;
constexpr float UmGalMarginSu = 24.0f;
constexpr float UmGalHeaderSu = 32.0f;
}  // namespace

bool UUmSkinGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("panel.bg.inset")));
    Background->SetPadding(FMargin(UmGalMarginSu));
    Grid = WidgetTree->ConstructWidget<UGridPanel>(UGridPanel::StaticClass(), TEXT("Grid"));
    Background->SetContent(Grid);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

FString UUmSkinGalleryWidget::Build(int32 Page, const FVector2D& CanvasSu, float PxPerSu) {
  if (!Grid) return TEXT("UMGALLERY skins failed: no grid");
  Grid->ClearChildren();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const int32 Total = S08HudTokens::kNumSkins;
  const int32 Rows = FMath::Max(1, FMath::FloorToInt((CanvasSu.Y - 2.0f * UmGalMarginSu - UmGalHeaderSu) / UmGalRowSu));
  PageCount = FMath::DivideAndRoundUp(Total, Rows);
  Page = FMath::Clamp(Page, 0, PageCount - 1);
  const bool bX2 = PxPerSu >= UUmHudTheme::SkinX2MinPxPerSu;
  const TCHAR* Heads[] = {TEXT("skin"), TEXT("x1 size"), TEXT("button"), TEXT("wide"), TEXT("x1 on cream"), TEXT("wide on cream")};
  for (int32 C = 0; C < UE_ARRAY_COUNT(Heads); ++C) {
    UmGalPut(Grid, UmGalText(*WidgetTree, Heads[C], TEXT("text.secondary")), 0, C, FMargin(0.0f, 0.0f, 16.0f, 8.0f));
  }
  int32 Textures = 0;
  for (int32 I = 0; I < Total; ++I) Textures += Theme.HasTextureSkin(S08HudTokens::kSkins[I].Name) ? 1 : 0;
  int32 Row = 1;
  for (int32 I = Page * Rows; I < FMath::Min(Total, (Page + 1) * Rows); ++I, ++Row) {
    const FName Key(S08HudTokens::kSkins[I].Name);
    const FSlateBrush* Brush = Theme.SkinFor(Key, PxPerSu);
    const bool bTexture = Theme.HasTextureSkin(Key);
    UmGalPut(Grid, UmGalText(*WidgetTree, Key.ToString() + (bTexture ? TEXT("") : TEXT(" (fallback)")), TEXT("text.primary")),
             Row, 0, FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    if (!Brush) continue;
    const FVector2D Native = Brush->ImageSize.X > 0 ? FVector2D(Brush->ImageSize) : FVector2D(34.0, 26.0);
    const bool bStretch = Brush->DrawAs == ESlateBrushDrawType::Box || Brush->DrawAs == ESlateBrushDrawType::RoundedBox;
    const FVector2D Sizes[] = {
        Native,
        bStretch ? FVector2D(FMath::Max(Native.X, 120.0), FMath::Max(Native.Y, 40.0)) : Native,
        bStretch ? FVector2D(FMath::Max(Native.X * 3.0, 200.0), FMath::Max(Native.Y * 1.5, 56.0)) : Native,
    };
    const int32 Cols[] = {1, 2, 3, 4, 5};
    const int32 SizeOf[] = {0, 1, 2, 0, 2};
    for (int32 K = 0; K < 5; ++K) {
      UBorder* Back = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
      Back->SetBrushColor(Theme.Color(K < 3 ? TEXT("card.navy") : TEXT("card.cream")));
      Back->SetPadding(FMargin(8.0f));
      USizeBox* Size = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
      Size->SetWidthOverride(static_cast<float>(Sizes[SizeOf[K]].X));
      Size->SetHeightOverride(static_cast<float>(Sizes[SizeOf[K]].Y));
      UImage* Image = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
      Image->SetBrush(*Brush);
      Size->AddChild(Image);
      Back->SetContent(Size);
      UmGalPut(Grid, Back, Row, Cols[K], FMargin(0.0f, 0.0f, 12.0f, 0.0f));
    }
  }
  return FString::Printf(TEXT("UMGALLERY skins page=%d/%d rows=%d pxPerSu=%.3f x2=%d textures=%d/%d"), Page + 1, PageCount,
                         Rows, PxPerSu, bX2 ? 1 : 0, Textures, Total);
}

bool UUmButtonGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("panel.bg.inset")));
    Background->SetPadding(FMargin(UmGalMarginSu));
    Grid = WidgetTree->ConstructWidget<UGridPanel>(UGridPanel::StaticClass(), TEXT("Grid"));
    Background->SetContent(Grid);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

TArray<FString> UUmButtonGalleryWidget::Build(const FVector2D& CanvasSu, int32 OnlyVariant) {
  TArray<FString> Lines;
  if (!Grid) return Lines;
  Grid->ClearChildren();
  Buttons.Reset();
  const EUmButtonState States[] = {EUmButtonState::Normal,  EUmButtonState::Hover, EUmButtonState::Pressed,
                                   EUmButtonState::Disabled, EUmButtonState::Focus, EUmButtonState::Selected,
                                   EUmButtonState::Busy};
  struct FRow {
    EUmButtonVariant Variant;
    const TCHAR* LabelKey;
    FName Icon;
    const TCHAR* KeyHint;
    const TCHAR* Why;
  };
  // real HUD strings (ST_Hud) and reasons (ST_Why) of the blocks that will use each variant
  const FRow Rows[] = {
      {EUmButtonVariant::Normal, TEXT("hud.combat.no.defense"), NAME_None, TEXT("hud.key.no_defense"), TEXT("why.deadline.passed")},
      {EUmButtonVariant::Primary, TEXT("hud.combat.defend"), NAME_None, TEXT("hud.key.confirm"), TEXT("why.defense.none")},
      {EUmButtonVariant::Disc, TEXT("hud.action.maneuver"), FName(TEXT("action-maneuver")), TEXT("hud.key.maneuver"), TEXT("why.not.your.turn")},
  };
  // as many states per line as the canvas holds (7 at 1920 su, 5 at 1137.8 su - 720p 150 %); each cell names its state
  constexpr float CellSu = 260.0f;
  constexpr float LabelColumnSu = 96.0f;
  const int32 States_ = UE_ARRAY_COUNT(States);
  const int32 PerLine = FMath::Clamp(FMath::FloorToInt((CanvasSu.X - 2.0f * UmGalMarginSu - LabelColumnSu) / CellSu), 3, States_);
  const int32 LinesPerRow = FMath::DivideAndRoundUp(States_, PerLine);
  int32 Shown = 0;
  for (int32 Ri = 0; Ri < UE_ARRAY_COUNT(Rows); ++Ri) {
    if (OnlyVariant >= 1 && OnlyVariant != Ri + 1) continue;  // one variant per page (720p 150 %)
    const int32 R = Shown++;
    UmGalPut(Grid, UmGalText(*WidgetTree, UmButtonVariantName(Rows[Ri].Variant), TEXT("text.secondary")), R * LinesPerRow, 0,
             FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    for (int32 C = 0; C < UE_ARRAY_COUNT(States); ++C) {
      UUmButton* Button = CreateWidget<UUmButton>(this, UUmButton::StaticClass());
      if (!Button) continue;
      const EUmButtonState S = States[C];
      FUmButtonModel M;
      M.Variant = Rows[Ri].Variant;
      M.Label = UmText::Get(EUmTable::Hud, Rows[Ri].LabelKey);
      M.IconName = Rows[Ri].Icon;
      M.KeyHint = UmText::Get(EUmTable::Hud, Rows[Ri].KeyHint);
      M.bEnabled = S != EUmButtonState::Disabled;
      M.Reason = S == EUmButtonState::Disabled ? FS09Reason::Make(Rows[Ri].Why) : FS09Reason();
      M.bSelected = S == EUmButtonState::Selected;
      M.bBusy = S == EUmButtonState::Busy;
      M.bFocused = S == EUmButtonState::Focus;
      Button->ApplyModel(M);
      Button->SetPreviewPointer(S == EUmButtonState::Hover, S == EUmButtonState::Pressed);
      UVerticalBox* Cell = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
      Cell->AddChildToVerticalBox(UmGalText(*WidgetTree, UmButtonStateName(S), TEXT("text.secondary")));
      if (UVerticalBoxSlot* ButtonSlot = Cell->AddChildToVerticalBox(Button)) {
        ButtonSlot->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 0.0f));
        ButtonSlot->SetHorizontalAlignment(HAlign_Left);
      }
      UmGalPut(Grid, Cell, R * LinesPerRow + C / PerLine, C % PerLine + 1, FMargin(0.0f, 8.0f, 16.0f, 8.0f));
      Buttons.Add(Button);
      Lines.Add(FString::Printf(TEXT("UMGALLERY button %s.%s: %s"), UmButtonVariantName(M.Variant), UmButtonStateName(S),
                                *Button->DescribeState()));
    }
  }
  Lines.Insert(FString::Printf(TEXT("UMGALLERY buttons variants=%d states=%d perLine=%d canvas=%.0fx%.0f page=%d"),
                               Shown, UE_ARRAY_COUNT(States), PerLine, CanvasSu.X, CanvasSu.Y, OnlyVariant),
               0);
  return Lines;
}

// ------------------------------------------------------------------------------- VS-2 HB-14...HB-16: the top strip

bool UUmTopStripGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("fx.dust")));  // a neutral mid tone under the navy plates
    Background->SetPadding(FMargin(UmGalMarginSu));
    Background->SetHorizontalAlignment(HAlign_Left);
    Background->SetVerticalAlignment(VAlign_Top);
    Rows = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Rows"));
    Background->SetContent(Rows);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

TArray<FString> UUmTopStripGalleryWidget::Build(const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Rows) return Lines;
  Rows->ClearChildren();
  Blocks.Reset();
  const FUmHudLayout Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, nullptr);
  const FBox2D TopRect = Layout.Rect(EUmHudBlock::Top);
  const FBox2D StatusRect = Layout.Rect(EUmHudBlock::Status);
  const FBox2D BannerRect = Layout.Rect(EUmHudBlock::Banner);
  auto Sized = [this](UWidget* Content, const FBox2D& Rect, bool bAutoHeight) {
    USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    Box->SetWidthOverride(static_cast<float>(Rect.Max.X - Rect.Min.X));
    if (!bAutoHeight) Box->SetHeightOverride(static_cast<float>(Rect.Max.Y - Rect.Min.Y));
    Box->SetContent(Content);
    return Box;
  };
  auto AddRow = [this](UWidget* W) {
    if (UVerticalBoxSlot* RowSlot = Rows->AddChildToVerticalBox(W)) {
      RowSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 8.0f));
      RowSlot->SetHorizontalAlignment(HAlign_Left);
    }
  };
  // ---- TOP: online, syncing, lost side by side (the same turn) ----
  UHorizontalBox* TopRow = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
  const EUmConnState Conns[] = {EUmConnState::Online, EUmConnState::Syncing, EUmConnState::Lost};
  for (const EUmConnState C : Conns) {
    UUmHudTop* Top = CreateWidget<UUmHudTop>(this, UUmHudTop::WidgetClass());
    if (!Top) continue;
    FUmTopModel M;
    M.TurnCount = 7;
    M.Conn = C;
    M.bClassS = Layout.bClassS;
    M.PxPerSu = PxPerSu;
    Top->ApplyModel(M);
    if (UHorizontalBoxSlot* S = TopRow->AddChildToHorizontalBox(Sized(Top, TopRect, false))) S->SetPadding(FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    Blocks.Add(Top);
    Lines.Add(FString::Printf(TEXT("UMGALLERY top conn=%s class=%s source=%s menu=%s"), UmConnection::StateName(C),
                              Layout.bClassS ? TEXT("S") : TEXT("L"), *Top->SourceName(),
                              Top->HasMenuGlyph() ? TEXT("glyph") : TEXT("word")));
  }
  AddRow(TopRow);
  // ---- STATUS: the six SHOT states (the first with the key chips of UI-ACC-017) ----
  struct FCase {
    const TCHAR* Name;
    FS09TurnStatusInput In;
    bool bKeys;
  };
  TArray<FCase> Cases;
  {
    FS09TurnStatusInput In;
    In.bViewerTurn = true;
    In.ActionsRemaining = 2;
    Cases.Add({TEXT("own+keys"), In, true});
    FS09TurnStatusInput Opp;
    Opp.OpponentVerb = ES09OpponentVerb::Turn;
    Opp.OpponentName = TEXT("King Arthur");
    Cases.Add({TEXT("opp"), Opp, false});
    FS09TurnStatusInput Defend;
    Defend.Mode = ES09CommandMode::CombatDefense;
    Cases.Add({TEXT("defend"), Defend, false});
    FS09TurnStatusInput Discard = In;
    Discard.Mode = ES09CommandMode::DiscardDraft;
    Discard.DiscardNeed = 2;
    Cases.Add({TEXT("discard"), Discard, false});
    FS09TurnStatusInput Choice = In;
    Choice.Mode = ES09CommandMode::PendingChoice;
    Choice.PendingPrompt = FS09Reason::Make(TEXT("ms.status.choice")).Arg(TEXT("choice"), TEXT("Можете усилить эту атаку."));
    Cases.Add({TEXT("choice"), Choice, false});
    FS09TurnStatusInput Sync = In;
    Sync.bSyncing = true;
    Cases.Add({TEXT("sync"), Sync, false});
  }
  for (const FCase& C : Cases) {
    UUmHudStatusLine* Status = CreateWidget<UUmHudStatusLine>(this, UUmHudStatusLine::WidgetClass());
    if (!Status) continue;
    FUmStatusFrame Frame;
    Frame.MaxWidthSu = static_cast<float>(StatusRect.Max.X - StatusRect.Min.X);
    Frame.PxPerSu = PxPerSu;
    Frame.bKeyHints = C.bKeys;
    Status->SetFrame(Frame);
    Status->ApplyModel(C.In);
    AddRow(Sized(Status, StatusRect, true));
    Blocks.Add(Status);
    Lines.Add(FString::Printf(TEXT("UMGALLERY status %s state=%s key=%s lines=%d size=%.0f width=%.0f height=%.0f"), C.Name,
                              UmHudStatus::StateName(Status->GetState()), *Status->GetLineKey().ToString(),
                              Status->GetFit().Lines, Status->GetFit().SizeSu, Status->GetBodySizeSu().X,
                              Status->GetBodySizeSu().Y));
  }
  // ---- BANNER at alpha 1 (an own turn 300 ms in) ----
  if (UUmHudBanner* Banner = CreateWidget<UUmHudBanner>(this, UUmHudBanner::WidgetClass())) {
    FS09TurnCue Cue;
    Cue.OnApplied(TEXT("them"), 1, TEXT("me"), false, 0.0, false);
    Cue.OnApplied(TEXT("me"), 2, TEXT("me"), false, 1000.0, false);
    Banner->SetPxPerSu(PxPerSu);
    Banner->ApplyModel(Cue, 1300.0);
    AddRow(Sized(Banner, BannerRect, false));
    Blocks.Add(Banner);
    Lines.Add(FString::Printf(TEXT("UMGALLERY banner alpha=%.2f source=%s"), Banner->GetAlpha(), *Banner->SourceName()));
  }
  Lines.Insert(FString::Printf(TEXT("UMGALLERY topstrip class=%s canvas=%.0fx%.0f pxPerSu=%.3f statusW=%.0f"),
                               Layout.bClassS ? TEXT("S") : TEXT("L"), CanvasSu.X, CanvasSu.Y, PxPerSu,
                               StatusRect.Max.X - StatusRect.Min.X),
               0);
  return Lines;
}

// ------------------------------------------------------------------------------- VS-2 HB-18...HB-21: the panels

bool UUmPanelsGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("fx.dust")));  // a neutral mid tone under the navy plates
    Background->SetPadding(FMargin(16.0f));
    Background->SetHorizontalAlignment(HAlign_Left);
    Background->SetVerticalAlignment(VAlign_Top);
    Rows = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Rows"));
    Background->SetContent(Rows);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

TArray<FString> UUmPanelsGalleryWidget::Build(int32 Page, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Rows) return Lines;
  Rows->ClearChildren();
  Blocks.Reset();
  KeepAlive.Reset();
  if (Page == 2) return BuildPortraits(CanvasSu, PxPerSu);
  const FUmHudLayout Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, nullptr);
  const bool bS = Layout.bClassS;
  const FBox2D LocRect = Layout.Rect(EUmHudBlock::PanelLoc);
  const FBox2D OppHandRect = Layout.Rect(EUmHudBlock::OppHand);
  const FVector2D PanelSize = LocRect.Max - LocRect.Min;
  const FVector2D HandSize = OppHandRect.Max - OppHandRect.Min;
  const FS08TurnHudLook Look = FS08TurnHudLook::FromCommandLine(FCommandLine::Get());
  const FS08ArtHudPlateStyle Chips;
  const bool bMedusaOwn = Page == 0;
  // the run I numbers of CX-09 (facts.json; the fallen / 0 HP / 3 and 10 backs / ≈ are states of the sheet)
  struct FHero {
    FString Name;
    FName Key;
    int32 Hp;
    int32 MaxHp;
    TArray<FUmSidekickView> Sidekicks;
  };
  FHero Medusa{TEXT("Medusa"), FName(TEXT("medusa")), 14, 16, {}};
  for (int32 I = 1; I <= 3; ++I) {
    FUmSidekickView S;
    S.Id = FString::Printf(TEXT("h%d"), I);
    S.Name = FString::Printf(TEXT("Harpies %d"), I);
    S.Key = FName(TEXT("medusa/harpies"));
    S.Number = I;
    S.Hp = 1;
    S.MaxHp = 1;
    Medusa.Sidekicks.Add(S);
  }
  FHero Arthur{TEXT("King Arthur"), FName(TEXT("king-arthur")), 17, 18, {}};
  {
    FUmSidekickView S;
    S.Id = TEXT("m");
    S.Name = TEXT("Merlin");
    S.Key = FName(TEXT("king-arthur/merlin"));
    S.Hp = 7;
    S.MaxHp = 7;
    Arthur.Sidekicks.Add(S);
  }
  const FHero& Own = bMedusaOwn ? Medusa : Arthur;
  const FHero& Opp = bMedusaOwn ? Arthur : Medusa;
  const int32 PerRow = FMath::Max(1, static_cast<int32>((CanvasSu.X - 32.0) / (PanelSize.X + 12.0)));
  UHorizontalBox* Row = nullptr;
  int32 InRow = 0;
  auto Cell = [&](UWidget* Content, const FVector2D& Size, const FString& Label) {
    if (!Row || InRow >= PerRow) {
      Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
      if (UVerticalBoxSlot* RS = Rows->AddChildToVerticalBox(Row)) RS->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 6.0f));
      InRow = 0;
    }
    UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    Box->AddChildToVerticalBox(UmGalText(*WidgetTree, Label, TEXT("card.navy")));
    USizeBox* Sized = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    Sized->SetWidthOverride(static_cast<float>(Size.X));
    Sized->SetHeightOverride(static_cast<float>(Size.Y));
    Sized->SetContent(Content);
    Box->AddChildToVerticalBox(Sized);
    if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Box)) S->SetPadding(FMargin(0.0f, 0.0f, 12.0f, 0.0f));
    ++InRow;
  };
  auto Panel = [&](EUmPanelSide Side, const FHero& H, EUmPanelState State, const TCHAR* Label,
                   TFunctionRef<void(UUmHudPlayerPanel&, FUmPlayerPanelModel&)> Tweak) {
    UUmHudPlayerPanel* P = CreateWidget<UUmHudPlayerPanel>(this, UUmHudPlayerPanel::WidgetClass(Side));
    if (!P) return (UUmHudPlayerPanel*)nullptr;
    P->Setup(Side, Look, Chips.TeamChipColor(Side == EUmPanelSide::Own ? 0 : 1));
    P->SetClockForTest([]() { return 0.0; });
    FUmPlayerPanelModel M;
    M.HeroName = H.Name;
    M.bHasHp = true;
    M.Hp = H.Hp;
    M.MaxHp = H.MaxHp;
    M.State = State;
    M.Sidekicks = H.Sidekicks;
    M.bClassS = bS;
    M.PxPerSu = PxPerSu;
    P->Portrait->SetPortrait(H.Key);
    P->Portrait->ApplyTracker(2, 0, true);
    if (Side == EUmPanelSide::Opp) P->Portrait->SetTrackerOpacity(State == EUmPanelState::Opp || State == EUmPanelState::Ai ? 1.0f : 0.0f);
    if (State == EUmPanelState::Own || State == EUmPanelState::Opp || State == EUmPanelState::Ai) P->Portrait->PlayRing(true);
    Tweak(*P, M);
    P->ApplyModel(M);
    Cell(P, PanelSize, FString::Printf(TEXT("%s %s"), Side == EUmPanelSide::Own ? TEXT("loc") : TEXT("opp"), Label));
    Blocks.Add(P);
    TArray<FString> Shot;
    P->CollectShotLines(Shot, FS08ScreenRect());
    Lines.Add(FString::Printf(TEXT("UMGALLERY panel %s %s"), Label, Shot.Num() ? *Shot[0] : TEXT("-")));
    // CP-09...CP-12: the hero circle and the sidekick mini portraits of this panel (ВР-CP10)
    const TCHAR* SideName = Side == EUmPanelSide::Own ? TEXT("own") : TEXT("opp");
    Lines.Add(FString::Printf(TEXT("UMGALLERY panel %s %s %s"), SideName, Label, *P->Portrait->PortraitShotLine(TEXT("panel"))));
    TArray<FString> Minis;
    P->CollectPortraitLines(Minis);
    for (const FString& M2 : Minis) Lines.Add(FString::Printf(TEXT("UMGALLERY panel %s %s %s"), SideName, Label, *M2));
    return P;
  };
  auto None = [](UUmHudPlayerPanel&, FUmPlayerPanelModel&) {};
  // ---- PANEL-LOC ----
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Own, TEXT("own-start+300"), [](UUmHudPlayerPanel& P, FUmPlayerPanelModel&) {
    P.Portrait->SetClockOverrideMs(0.0f);
    P.Portrait->PlayRing(false);
    P.Portrait->SetClockOverrideMs(300.0f);
  });
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Own, TEXT("own"), None);
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Wait, TEXT("wait"), None);
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Own, TEXT("action-filled-2"), [bMedusaOwn](UUmHudPlayerPanel& P, FUmPlayerPanelModel&) {
    const FName Type(bMedusaOwn ? TEXT("maneuver") : TEXT("attack"));
    P.Portrait->SetClockOverrideMs(0.0f);
    P.Portrait->ApplyTracker(2, 2, false, {Type, Type});
    P.Portrait->SetClockOverrideMs(400.0f);
  });
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Own, TEXT("damage+320"), [](UUmHudPlayerPanel& P, FUmPlayerPanelModel& M) {
    M.Hp -= 1;
    P.Portrait->SetClockOverrideMs(0.0f);
    P.Portrait->PlayHeart(TEXT("damage"));
    P.Portrait->SetClockOverrideMs(320.0f);
  });
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Fallen, TEXT("fallen"), [](UUmHudPlayerPanel& P, FUmPlayerPanelModel& M) {
    M.Hp = 0;
    P.Portrait->SetHeartFallen(true, true);
  });
  UUmHudPlayerPanel* SidekickFallen =
      Panel(EUmPanelSide::Own, Own, EUmPanelState::Own, TEXT("sidekick-fallen"), [](UUmHudPlayerPanel&, FUmPlayerPanelModel& M) {
        if (M.Sidekicks.Num()) {
          M.Sidekicks[0].bFallen = true;
          M.Sidekicks[0].Hp = 0;
        }
      });
  Panel(EUmPanelSide::Own, Own, EUmPanelState::Own, TEXT("no-avatar"), [](UUmHudPlayerPanel& P, FUmPlayerPanelModel&) {
    P.Portrait->SetPortrait(NAME_None);  // the monogram fallback (CP-08)
  });
  if (bS && SidekickFallen && SidekickFallen->GetSidekickTooltip()) {
    // class S: the sidekicks live in the panel's tooltip (ВР-VS2-CX09-06) - shown here as a cell of its own
    UWidget* Tip = SidekickFallen->GetSidekickTooltip();
    SidekickFallen->SetToolTip(nullptr);
    Cell(Tip, FVector2D(180.0, 48.0 + 22.0 * FMath::Max(0, SidekickFallen->GetTooltipRows() - 1)), TEXT("S tooltip"));
  }
  Row = nullptr;
  // ---- PANEL-OPP ----
  Panel(EUmPanelSide::Opp, Opp, EUmPanelState::Opp, TEXT("opp"), [bMedusaOwn](UUmHudPlayerPanel& P, FUmPlayerPanelModel&) {
    const FName Type(bMedusaOwn ? TEXT("attack") : TEXT("maneuver"));
    P.Portrait->ApplyTracker(2, 1, true, {Type});
  });
  Panel(EUmPanelSide::Opp, Opp, EUmPanelState::Wait, TEXT("wait"), None);
  Panel(EUmPanelSide::Opp, Opp, EUmPanelState::Ai, TEXT("ai"), None);
  Panel(EUmPanelSide::Opp, Opp, EUmPanelState::Fallen, TEXT("fallen"), [](UUmHudPlayerPanel& P, FUmPlayerPanelModel& M) {
    M.Hp = 0;
    P.Portrait->SetHeartFallen(true, true);
  });
  Row = nullptr;
  // ---- OPP-HAND: the opponent's backs ----
  struct FHand {
    const TCHAR* Label;
    int32 Count;
    bool bStale;
  };
  const FHand Hands[] = {{TEXT("3"), 3, false}, {TEXT("5"), 5, false}, {TEXT("10"), 10, false}, {TEXT("stale"), 5, true}};
  for (const FHand& H : Hands) {
    UUmHudOppHand* Hand = CreateWidget<UUmHudOppHand>(this, UUmHudOppHand::WidgetClass());
    if (!Hand) continue;
    Hand->SetClockForTest([]() { return 0.0; });
    FUmOppHandModel M;
    M.HandCount = H.Count;
    M.DeckCount = bMedusaOwn ? 24 : 23;
    M.DiscardCount = bMedusaOwn ? 1 : 2;
    M.bDeckStale = H.bStale;
    M.HeroSlug = Opp.Key.ToString();
    M.WidthSu = static_cast<float>(HandSize.X);
    M.PxPerSu = PxPerSu;
    Hand->ApplyModel(M);
    Cell(Hand, HandSize, FString::Printf(TEXT("opphand %s"), H.Label));
    Blocks.Add(Hand);
    TArray<FString> Shot;
    Hand->CollectShotLines(Shot, FS08ScreenRect());
    Lines.Add(FString::Printf(TEXT("UMGALLERY opphand %s %s"), H.Label, Shot.Num() ? *Shot[0] : TEXT("-")));
  }
  Lines.Insert(FString::Printf(TEXT("UMGALLERY panels page=%d own=%s class=%s canvas=%.0fx%.0f pxPerSu=%.3f panel=%.0fx%.0f "
                                    "opphand=%.0fx%.0f perRow=%d %s"),
                               Page + 1, *Own.Name.Replace(TEXT(" "), TEXT("_")), bS ? TEXT("S") : TEXT("L"), CanvasSu.X,
                               CanvasSu.Y, PxPerSu, PanelSize.X, PanelSize.Y, HandSize.X, HandSize.Y, PerRow, *Look.Describe()),
               0);
  return Lines;
}

// ------------------------------------------------------------------------- VS-2 CP-09...CP-12: the portrait sizes

TArray<FString> UUmPanelsGalleryWidget::BuildPortraits(const FVector2D& CanvasSu, float PxPerSu) {
  // one row per character: every show size of 02 §6.4 / 04 §1.4-§1.10 in the circle of the accepted CP-07 crop (the
  // registry disc), the states (fallen, loser) and the fallback; the harpies with their badges 1-3 (ВР-72). The real
  // M_UmPortraitDisc at the window's px per su - a sheet at 720p / 1080p / 2160p is the x0.67 / x1 / x2 sheet of the
  // cards; at 2160p 150 % (x3) the ВР-CP04 cap shows (capped=1). Review only (editor -game), not acceptance frames.
  TArray<FString> Lines;
  struct FCellDef {
    float Su;
    EUmPortraitState State;
    const TCHAR* Show;
    const TCHAR* Caption;
    int32 Number;  // the harpy's badge / fallback digit
    bool bNoPng;   // the fallback (drawn as if the PNG were missing)
    bool bBadge;
  };
  struct FRowDef {
    const TCHAR* Title;
    FName Key;
    const TCHAR* Name;
    TArray<FCellDef> Cells;
  };
  const EUmPortraitState A = EUmPortraitState::Avatar, F = EUmPortraitState::Fallen, L = EUmPortraitState::Loser;
  const TArray<FCellDef> HeroCells = {
      {32.0f, A, TEXT("lobby"), TEXT("32 lobby"), 0, false, false},
      {64.0f, A, TEXT("panel"), TEXT("64 S"), 0, false, false},
      {80.0f, A, TEXT("panel"), TEXT("80 panel"), 0, false, false},
      {120.0f, A, TEXT("room"), TEXT("120 room"), 0, false, false},
      {160.0f, A, TEXT("loading"), TEXT("160 load"), 0, false, false},
      {120.0f, L, TEXT("result"), TEXT("120 loser"), 0, false, false},
      {80.0f, F, TEXT("panel"), TEXT("80 fallen"), 0, false, false},
      {80.0f, A, TEXT("panel"), TEXT("80 no PNG"), 0, true, false}};
  const TArray<FRowDef> RowDefs = {
      {TEXT("CP-09 King Arthur"), FName(TEXT("king-arthur")), TEXT("King Arthur"), HeroCells},
      {TEXT("CP-11 Medusa"), FName(TEXT("medusa")), TEXT("Medusa"), HeroCells},
      {TEXT("CP-10 Merlin"), FName(TEXT("king-arthur/merlin")), TEXT("Merlin"),
       {{32.0f, A, TEXT("panel"), TEXT("32"), 0, false, false},
        {40.0f, A, TEXT("room"), TEXT("40 room"), 0, false, false},
        {32.0f, F, TEXT("panel"), TEXT("32 fallen"), 0, false, false},
        {40.0f, F, TEXT("room"), TEXT("40 fallen"), 0, false, false},
        {32.0f, A, TEXT("panel"), TEXT("32 no PNG"), 0, true, false}}},
      {TEXT("CP-12 Harpies"), FName(TEXT("medusa/harpies")), TEXT("Harpies"),
       {{32.0f, A, TEXT("panel"), TEXT("1"), 1, false, true},
        {32.0f, A, TEXT("panel"), TEXT("2"), 2, false, true},
        {32.0f, A, TEXT("panel"), TEXT("3"), 3, false, true},
        {32.0f, F, TEXT("panel"), TEXT("2 fallen"), 2, false, true},
        {40.0f, A, TEXT("room"), TEXT("40 room"), 0, false, false},
        {40.0f, F, TEXT("room"), TEXT("40 fallen"), 0, false, false},
        {32.0f, A, TEXT("panel"), TEXT("no PNG 1"), 1, true, false},
        {32.0f, A, TEXT("panel"), TEXT("no PNG 2"), 2, true, false},
        {32.0f, A, TEXT("panel"), TEXT("no PNG 3"), 3, true, false}}},
  };
  for (const FRowDef& R : RowDefs) {
    UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    if (UVerticalBoxSlot* RS = Rows->AddChildToVerticalBox(Row)) RS->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 16.0f));
    USizeBox* TitleBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    TitleBox->SetWidthOverride(150.0f);
    TitleBox->SetContent(UmGalText(*WidgetTree, R.Title, TEXT("card.navy")));
    if (UHorizontalBoxSlot* TS = Row->AddChildToHorizontalBox(TitleBox)) TS->SetVerticalAlignment(VAlign_Top);
    for (const FCellDef& C : R.Cells) {
      UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
      Box->AddChildToVerticalBox(UmGalText(*WidgetTree, C.Caption, TEXT("card.navy")));
      FUmPortraitDiscSpec Spec;
      Spec.Key = R.Key;
      Spec.Name = R.Name;
      Spec.Number = C.Number;
      Spec.ShowSu = C.Su;
      Spec.PxPerSu = PxPerSu;
      Spec.State = C.State;
      Spec.bLegacy = C.bNoPng;  // the fallback look without the PNG (and without a Warning: the sheet asks for it)
      FUmPortraitShown Shown;
      UWidget* Content = UmPortrait::MakeDisc(*WidgetTree, this, Spec, Shown, KeepAlive);
      if (C.bNoPng) Shown.Tex = TEXT("monogram-sheet");
      if (C.bBadge && Shown.IsAvatar()) {
        // the panel's placement (CX-09, UUmHudPlayerPanel::RebuildSidekicks): the badge at (+21, +20)
        USizeBox* StackBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        StackBox->SetWidthOverride(C.Su + 3.0f);
        StackBox->SetHeightOverride(C.Su + 2.0f);
        UOverlay* Stack = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass());
        StackBox->SetContent(Stack);
        if (UOverlaySlot* P = Stack->AddChildToOverlay(Content)) {
          P->SetHorizontalAlignment(HAlign_Left);
          P->SetVerticalAlignment(VAlign_Top);
        }
        if (UOverlaySlot* X = Stack->AddChildToOverlay(UmPortrait::MakeNumberBadge(*WidgetTree, C.Number))) {
          X->SetHorizontalAlignment(HAlign_Left);
          X->SetVerticalAlignment(VAlign_Top);
          X->SetPadding(FMargin(21.0f, 20.0f, 0.0f, 0.0f));
        }
        Content = StackBox;
      }
      if (UVerticalBoxSlot* DS = Box->AddChildToVerticalBox(Content)) {
        DS->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 0.0f));
        DS->SetHorizontalAlignment(HAlign_Left);  // the circle at its own size under a wider caption
      }
      if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Box)) {
        S->SetPadding(FMargin(0.0f, 0.0f, 16.0f, 0.0f));
        S->SetVerticalAlignment(VAlign_Top);
      }
      Lines.Add(FString::Printf(TEXT("UMGALLERY portrait %s %s"), *FString(C.Caption).Replace(TEXT(" "), TEXT("_")),
                                *Shown.Line(C.Show, TEXT("own"))));
    }
  }
  Lines.Insert(FString::Printf(TEXT("UMGALLERY portraits page=3 canvas=%.0fx%.0f pxPerSu=%.3f rows=%d"), CanvasSu.X,
                               CanvasSu.Y, PxPerSu, RowDefs.Num()),
               0);
  return Lines;
}

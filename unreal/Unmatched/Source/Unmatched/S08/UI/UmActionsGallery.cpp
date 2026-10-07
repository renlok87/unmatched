// VS-4 HB-43 review sheet - see UmActionsGallery.h.
#include "UmActionsGallery.h"

#include "UmButton.h"
#include "UmCardMedia.h"
#include "UmCursor.h"
#include "UmDecksGallery.h"
#include "UmGameHud.h"
#include "UmHandGallery.h"
#include "UmHudDecks.h"
#include "UmHudTheme.h"
#include "UmHudTop.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

namespace UmActionsGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("own-2"),        TEXT("own-2-why"),         TEXT("own-1-why"),   TEXT("own-0"),
                                           TEXT("own-0-why"),    TEXT("mode-maneuver"),     TEXT("mode-maneuver-why"),
                                           TEXT("mode-attack"),  TEXT("mode-scheme"),       TEXT("discard-why"), TEXT("opp"),
                                           TEXT("opp-why"),      TEXT("hover"),             TEXT("focus"),       TEXT("keys"),
                                           TEXT("keys-own-0")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}

FUmActionsInput StateInput(int32 State, bool bClassS, int32& OutPointer) {
  // HB-42 A4 / A5 (ВР-VS2-HB42-05, -06): the numbers are parameters of the component - n = 2 / 1 from
  // ACTIONS_PER_TURN = 2, need 1 / have 0 the smallest hand-limit case (hand 8, limit 7)
  constexpr int32 M = static_cast<int32>(EUmActionKey::Maneuver);
  constexpr int32 A = static_cast<int32>(EUmActionKey::Attack);
  constexpr int32 E = static_cast<int32>(EUmActionKey::EndTurn);
  FUmActionsInput In;
  In.bShow = true;
  In.bViewerTurn = true;
  OutPointer = INDEX_NONE;
  auto Remaining = [&In](int32 N) {
    In.ActionsRemaining = N;
    In.EndTurn = N > 0 ? FS09Reason::Make(TEXT("why.actions.remaining")).Arg(TEXT("n"), N) : FS09Reason();
    if (N == 0) In.BeginRefusal = FS09Reason::Make(TEXT("why.no.actions"));
  };
  switch (State) {
    case 0: Remaining(2); break;
    case 1: Remaining(2); OutPointer = E; break;
    case 2: Remaining(1); OutPointer = E; break;
    case 3: Remaining(0); break;
    case 4: Remaining(0); OutPointer = A; break;
    case 5:
    case 6:
      Remaining(2);
      In.Mode = ES09CommandMode::ManeuverDraft;
      In.EndTurn = FS09Reason::Make(TEXT("why.draft.open"));
      In.BeginRefusal = FS09Reason::Make(TEXT("why.draft.open"));
      if (State == 6) OutPointer = E;
      break;
    case 7: Remaining(2); In.Mode = ES09CommandMode::AttackDraft; break;
    case 8: Remaining(1); In.Mode = ES09CommandMode::SchemeChoice; break;
    case 9:
      Remaining(0);
      In.Mode = ES09CommandMode::DiscardDraft;
      In.EndTurn = FS09Reason::Make(TEXT("why.discard.count")).Arg(TEXT("need"), 1).Arg(TEXT("have"), 0);
      OutPointer = E;
      break;
    case 10: In.bViewerTurn = false; break;
    case 11: In.bViewerTurn = false; OutPointer = A; break;
    case 12: Remaining(2); OutPointer = M; break;
    case 13: Remaining(2); In.FocusIndex = M; break;
    case 14: Remaining(2); In.bKeyHints = true; if (bClassS) OutPointer = M; break;
    case 15: Remaining(0); In.bKeyHints = true; if (bClassS) OutPointer = E; break;
    default: break;
  }
  return In;
}
}  // namespace UmActionsGallery

namespace {
FS09CardView UmAgCard(const FS09DeckList& List, const FString& Slug, const TCHAR* Name, int32 Copy) {
  FS09CardView V;
  V.Name = Name;
  V.InstanceId = FString::Printf(TEXT("gallery::%s::%s-%d"), *Slug, Name, Copy);
  for (const FS09DeckListCard& C : List.Cards) {
    if (C.Name != Name) continue;
    V.CardId = C.CardId;
    V.NameRu = C.NameRu;
    V.CardType = C.CardType;
    V.BannerName = C.BannerName;
    V.AttackValue = FMath::Max(0, C.AttackValue);
    V.DefenseValue = FMath::Max(0, C.DefenseValue);
    V.BoostValue = FMath::Max(0, C.BoostValue);
    V.bHasBoostValue = C.BoostValue >= 0;
    V.bVisible = true;
    break;
  }
  return V;
}
}  // namespace

bool UUmActionsGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

TArray<FString> UUmActionsGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    Lines.Add(TEXT("UMGALLERY actions canvas=0x0"));
    return Lines;
  }
  Root->ClearChildren();
  BoardNow = Board.ToLower();
  PxNow = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  const FBox2D Field = UmHandGallery::FieldSu(BoardNow, CanvasSu, PxPerSu);
  Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, &Field);
  Layout.bEnglishChips = UmCardMedia::PreferredLang() == TEXT("en");
  const FString Rel = bSarpedon ? TEXT("docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png")
                                : TEXT("docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png");
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / Rel);
  // -S08IconGalleryHandPlain: no picture (the sheet that may go to git; with -S08CardArtLegacy no scan / back either)
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
  Game = CreateWidget<UUmGameHud>(this, UUmGameHud::StaticClass());
  if (Game) {
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Game)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
      S->SetOffsets(FMargin(0.0f));
    }
    // TOP (IC-55: «Журнал» in class S), DECKS (the HB-26 chips, ВР-VS2-HB42-10), ACTIONS
    Top = CreateWidget<UUmHudTop>(this, UUmHudTop::WidgetClass());
    if (Top) {
      Game->SetBlock(EUmGameSlot::Top, Top);
      FUmTopModel TM;
      TM.TurnCount = 3;  // run I: the own turn 3 of Medusa (HB-38 facts), the turn text of TOP
      TM.bClassS = Layout.bClassS;
      TM.PxPerSu = PxPerSu;
      Top->ApplyModel(TM);
    }
    Decks = CreateWidget<UUmHudDecks>(this, UUmHudDecks::WidgetClass());
    if (Decks) {
      Game->SetBlock(EUmGameSlot::Decks, Decks);
      Decks->SetSyncLoad(true);
      FUmDecksFrame F;
      F.bClassS = Layout.bClassS;
      F.PxPerSu = PxPerSu;
      F.RectSu = Layout.Rect(EUmHudBlock::Decks);
      F.bEnglish = Layout.bEnglishChips;
      Decks->SetFrame(F);
      const FString Slug = bSarpedon ? TEXT("king-arthur") : TEXT("medusa");
      const FS09DeckList List = UmDecksGallery::LoadList(Slug, TEXT("gallery-own"));
      FS09PlayerPanel Own;
      Own.PlayerId = TEXT("gallery-own");
      Own.bIsViewer = true;
      Own.DeckCount = bSarpedon ? 25 : 23;
      if (bSarpedon) {
        Own.Discard.Add(UmAgCard(List, Slug, TEXT("Momentous Shift"), 0));
        Own.Discard.Add(UmAgCard(List, Slug, TEXT("Swift Strike"), 1));
      } else {
        Own.Discard.Add(UmAgCard(List, Slug, TEXT("A Momentary Glance"), 0));
        Own.Discard.Add(UmAgCard(List, Slug, TEXT("Feint"), 0));
      }
      Decks->ApplyModel(UmHudDecks::Gather(&Own, Slug));
    }
    Actions = CreateWidget<UUmHudActions>(this, UUmHudActions::WidgetClass());
    if (Actions) {
      Game->SetBlock(EUmGameSlot::Actions, Actions);
      FUmActionsFrame F;
      F.bClassS = Layout.bClassS;
      F.PxPerSu = PxPerSu;
      F.RectSu = Layout.Rect(EUmHudBlock::Actions);
      F.CanvasSu = Layout.CanvasSu;
      F.MarginSu = Layout.MarginSu;
      Actions->SetFrame(F);
      Actions->SetTipImmediateForTest(true);  // a still sheet: the tooltip at once
    }
    Game->ApplyLayout(Layout, TArray<FName>(), false);
  }
  CursorImage = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Cursor")));
  CursorImage->SetVisibility(ESlateVisibility::Collapsed);
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(CursorImage)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetZOrder(1000);
  }
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(Layout.MarginSu, CanvasSu.Y - Layout.MarginSu - 24.0));  // bottom left: off the figures
  }
  StateNow = -1;
  Lines.Add(FString::Printf(TEXT("UMGALLERY actions board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s class=%s"), *BoardNow,
                            CanvasSu.X, CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"),
                            Layout.bClassS ? TEXT("S") : TEXT("L")));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

void UUmActionsGalleryWidget::ApplyState(int32 State, TArray<FString>& Lines) {
  if (!Actions) return;
  int32 Pointer = INDEX_NONE;
  const FUmActionsInput In = UmActionsGallery::StateInput(State, Layout.bClassS, Pointer);
  Actions->ApplyModel(UmHudActions::Decide(In));
  Actions->SimulatePointer(Pointer);
  Actions->TickForTest();
  // the software cursor of the pointed cell (04 §3.2): the pointer over an enabled cell, «недоступно» over a disabled
  // one - the texture of this DPI x UI scale drawn 1 : 1, its hot spot on the cell centre
  if (CursorImage) {
    CursorImage->SetVisibility(ESlateVisibility::Collapsed);
    if (Pointer != INDEX_NONE) {
      const bool bEnabled = Actions->GetModel().Buttons[Pointer].bEnabled;
      const EUmCursor Shape = bEnabled ? EUmCursor::Pointer : EUmCursor::Denied;
      const int32 Px = UmCursor::SizePx(PxNow);
      UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *UmCursor::TexturePath(Shape, Px));
      FIntPoint Hot(0, 0);
      UmCursor::Hotspot(Shape, Px, Hot);
      if (Tex) {
        CursorImage->SetBrushFromTexture(Tex);
        const FBox2D Cell = Actions->CellRectSu(static_cast<EUmActionKey>(Pointer));
        const FVector2D At = Cell.GetCenter();
        if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(CursorImage->Slot)) {
          S->SetAutoSize(false);
          S->SetPosition(At - FVector2D(Hot.X, Hot.Y) / PxNow);
          S->SetSize(FVector2D(Px, Px) / PxNow);
        }
        CursorImage->SetVisibility(ESlateVisibility::HitTestInvisible);
        Lines.Add(FString::Printf(TEXT("UMGALLERY actions cursor=%s px=%d hot=(%d,%d) at=(%.1f,%.1f)"), UmCursor::Name(Shape), Px,
                                  Hot.X, Hot.Y, At.X, At.Y));
      }
    }
  }
}

TArray<FString> UUmActionsGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  if (!Actions) return Lines;
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmActionsGallery::StateCount - 1);
  if (State != StateNow) {
    StateNow = State;
    ApplyState(State, Lines);
    if (Label) {
      Label->SetText(FText::FromString(FString::Printf(TEXT("HB-43 sheet · %s · %s (review tooling, not an acceptance frame)"),
                                                       *BoardNow, UmActionsGallery::StateName(State))));
    }
  }
  Actions->TickForTest();
  Lines.Add(FString::Printf(TEXT("UMGALLERY actions board=%s state=%d:%s t=%.0f"), *BoardNow, State, UmActionsGallery::StateName(State), TMs));
  Actions->CollectShotLines(Lines);
  if (Decks) Decks->CollectShotLines(Lines);
  return Lines;
}

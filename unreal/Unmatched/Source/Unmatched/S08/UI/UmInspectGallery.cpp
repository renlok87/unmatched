// VS-4 V4 (H13) review sheet - see UmInspectGallery.h.
#include "UmInspectGallery.h"

#include "UmCardMedia.h"
#include "UmDecksGallery.h"
#include "UmHandGallery.h"
#include "UmHudTheme.h"
#include "UmScreenInspect.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

namespace UmInspectGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("own"), TEXT("own-en"), TEXT("loading"), TEXT("missing"), TEXT("hidden"),
                                           TEXT("deck"), TEXT("deck-end"), TEXT("deck-card"), TEXT("deck-ka"), TEXT("opp-card")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}
}  // namespace UmInspectGallery

namespace {
/** A card of a list as a hand / pile instance (the HB-26 moment of UmDecksGallery). */
FS09CardView UmIgCard(const FS09DeckList& List, const TCHAR* Name, int32 Copy) {
  FS09CardView V;
  for (const FS09DeckListCard& C : List.Cards) {
    if (C.Name != Name) continue;
    V = UmInspect::DeckCardView(C);
    break;
  }
  V.InstanceId = FString::Printf(TEXT("gallery::%s-%d"), Name, Copy);
  return V;
}

int32 UmIgIndex(const FS09DeckList& List, const TCHAR* Name) {
  return List.Cards.IndexOfByPredicate([Name](const FS09DeckListCard& C) { return C.Name == Name; });
}
}  // namespace

bool UUmInspectGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

TArray<FString> UUmInspectGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    Lines.Add(TEXT("UMGALLERY inspect pending canvas=0x0"));
    return Lines;
  }
  BoardNow = Board.ToLower();
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  const FBox2D Field = UmHandGallery::FieldSu(BoardNow, CanvasSu, PxPerSu);
  Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, &Field);
  Medusa = UmDecksGallery::LoadList(TEXT("medusa"), TEXT("gallery-medusa"));
  Arthur = UmDecksGallery::LoadList(TEXT("king-arthur"), TEXT("gallery-arthur"));
  const FString Rel = bSarpedon ? TEXT("docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png")
                                : TEXT("docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png");
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / Rel);
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
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  Lines.Add(FString::Printf(TEXT("UMGALLERY inspect board=%s canvas=%.0fx%.0f pxPerSu=%.3f class=%s background=%s medusa=%d/%d arthur=%d/%d"),
                            *BoardNow, CanvasSu.X, CanvasSu.Y, PxPerSu, Layout.bClassS ? TEXT("S") : TEXT("L"),
                            BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"), Medusa.Cards.Num(), UmInspect::CopiesSum(Medusa.Cards),
                            Arthur.Cards.Num(), UmInspect::CopiesSum(Arthur.Cards)));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

void UUmInspectGalleryWidget::ApplyState(int32 State, double TMs) {
  // a fresh modal per state (a load held for «loading» never leaks into the next state)
  if (Screen) Screen->RemoveFromParent();
  Screen = CreateWidget<UUmScreenInspect>(this, UUmScreenInspect::WidgetClass());
  if (!Screen) return;
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Screen)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
    S->SetOffsets(FMargin(0.0f));
  }
  if (Label && !Label->GetParent()) {
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
      S->SetAutoSize(true);
      S->SetPosition(FVector2D(Layout.MarginSu, Layout.MarginSu * 0.25f));
    }
  }
  Screen->SetSyncLoadForSheet(State != 2);
  Screen->SetSheetClockMs(TMs);
  Screen->ApplyCanvas(Layout.CanvasSu, Layout.bClassS, Layout.PxPerSu);
  // the HB-26 moment: own Medusa - Gaze of Stone x2 in the hand, A Momentary Glance and Feint in the discard
  FS09PlayerPanel Own;
  Own.PlayerId = TEXT("gallery-medusa");
  Own.bIsViewer = true;
  Own.Cards.Add(UmIgCard(Medusa, TEXT("Gaze of Stone"), 0));
  Own.Cards.Add(UmIgCard(Medusa, TEXT("Gaze of Stone"), 1));
  for (const TCHAR* N : {TEXT("Snipe"), TEXT("Clutching Claws"), TEXT("Dash")}) Own.Cards.Add(UmIgCard(Medusa, N, 0));
  Own.Discard.Add(UmIgCard(Medusa, TEXT("A Momentary Glance"), 0));
  Own.Discard.Add(UmIgCard(Medusa, TEXT("Feint"), 0));
  FS09PlayerPanel Opp;
  Opp.PlayerId = TEXT("gallery-arthur");
  Opp.HandCount = 5;
  Opp.Discard.Add(UmIgCard(Arthur, TEXT("Swift Strike"), 0));
  TArray<FS09DeckList> Lists = {Medusa, Arthur};
  FUmInspectContext C;
  C.Own = &Own;
  C.Opp = &Opp;
  C.OwnHero = TEXT("Medusa");
  C.OwnSlug = TEXT("medusa");
  C.OppHero = TEXT("King Arthur");
  C.OppSlug = TEXT("king-arthur");
  C.Lists = &Lists;
  FUmInspectModel M;
  switch (State) {
    case 0:
    case 1:
    case 2:
      M = UmInspect::FromCard(Own.Cards[0], EUmInspectSource::Sheet, C);
      break;
    case 3:
      M = UmInspect::FromCard(Own.Cards[0], EUmInspectSource::Sheet, C);
      M.HeroSlug.Reset();  // no scan key: the hero is not known yet (INT-018 fallback)
      break;
    case 4: {
      // the viewer King Arthur, the hidden card of Medusa (a face-down defense / boost / her hand)
      FS09CardView Hidden;
      Hidden.bHidden = true;
      FUmInspectContext K = C;
      K.Own = &Opp;
      K.Opp = &Own;
      K.OwnHero = C.OppHero;
      K.OwnSlug = C.OppSlug;
      K.OppHero = C.OwnHero;
      K.OppSlug = C.OwnSlug;
      M = UmInspect::FromCard(Hidden, EUmInspectSource::Sheet, K);
      break;
    }
    case 5:
    case 6:
    case 7:
      M = UmInspect::FromDeck(true, EUmInspectSource::Sheet, C);
      break;
    case 8:
      M = UmInspect::FromDeck(false, EUmInspectSource::Sheet, C);
      break;
    default:
      M = UmInspect::FromCard(Opp.Discard[0], EUmInspectSource::Sheet, C);
      break;
  }
  if (State == 2) {
    if (Screen->Card) Screen->Card->SetHoldLoadingForSheet(true);
  }
  Screen->Open(M);
  if (State == 1) Screen->HandleKey(EKeys::Tab);
  if (State == 6) {
    while (Screen->WheelStep(false)) {
    }
  }
  if (State == 7) Screen->OpenDeckCard(UmIgIndex(Medusa, TEXT("Hiss and Slither")));
  // shown at alpha 1 (the 250 ms appear and the 150 ms switch are over)
  Screen->SetSheetClockMs(TMs + 1000.0);
  Screen->Step();
  Screen->StepInspect();
}

TArray<FString> UUmInspectGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  if (BoardNow.IsEmpty()) return Lines;  // not built yet (the canvas arrives with the first window apply)
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmInspectGallery::StateCount - 1);
  if (State != StateNow) {
    StateNow = State;
    ApplyState(State, 1000.0 * State);
    if (Label) {
      Label->SetText(FText::FromString(FString::Printf(TEXT("SC-21/22/23 + CP-22 sheet · %s · %s (review tooling, not an acceptance frame)"),
                                                       *BoardNow, UmInspectGallery::StateName(State))));
    }
  }
  if (!Screen) return Lines;
  // the clock of the second: the loading spinner appears at + 300 ms (HB-47)
  Screen->SetSheetClockMs(TMs + (State == 2 ? 0.0 : 1000.0));
  Screen->Step();
  Screen->StepInspect();
  if (Screen->Card) Screen->Card->Step();
  Lines.Add(FString::Printf(TEXT("UMGALLERY inspect board=%s state=%d:%s t=%.0f"), *BoardNow, State, UmInspectGallery::StateName(State), TMs));
  Screen->CollectShotLines(Lines);
  return Lines;
}

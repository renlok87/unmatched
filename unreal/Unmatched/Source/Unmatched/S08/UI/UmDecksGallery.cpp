// VS-3 HB-27 / HB-28 / HB-47 review sheet - see UmDecksGallery.h.
#include "UmDecksGallery.h"

#include "UmCardGallery.h"
#include "UmCardMedia.h"
#include "UmHandGallery.h"
#include "UmHudDeckPanel.h"
#include "UmHudDecks.h"
#include "UmHudHand.h"
#include "UmHudTheme.h"
#include "UmSkeletonRows.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace UmDecksGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("chips"), TEXT("chips-stale"), TEXT("own"), TEXT("own-end"), TEXT("own-discard"),
                                           TEXT("opp"), TEXT("opp-end"), TEXT("loading"), TEXT("failed"),
                                           TEXT("empty-discard"), TEXT("own-fan9")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}

FS09DeckList LoadList(const FString& HeroSlug, const FString& PlayerId) {
  FS09DeckList List;
  List.PlayerId = PlayerId;
  const FString Path = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S01"), TEXT("content-") + HeroSlug + TEXT(".json")));
  FString Text;
  TSharedPtr<FJsonObject> Root;
  if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) ||
      !Root.IsValid()) {
    return List;
  }
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!Root->TryGetArrayField(TEXT("cards"), Cards)) return List;
  auto IntOr = [](const TSharedPtr<FJsonObject>& C, const TCHAR* Field) {
    double N = 0.0;
    return C->TryGetNumberField(Field, N) ? static_cast<int32>(N) : -1;
  };
  for (const TSharedPtr<FJsonValue>& V : *Cards) {
    const TSharedPtr<FJsonObject> C = V.IsValid() ? V->AsObject() : nullptr;
    if (!C.IsValid()) continue;
    FS09DeckListCard Card;
    C->TryGetStringField(TEXT("id"), Card.CardId);
    C->TryGetStringField(TEXT("name"), Card.Name);
    C->TryGetStringField(TEXT("nameRu"), Card.NameRu);
    C->TryGetStringField(TEXT("cardType"), Card.CardType);
    C->TryGetStringField(TEXT("bannerName"), Card.BannerName);
    Card.AttackValue = IntOr(C, TEXT("attackValue"));
    Card.DefenseValue = IntOr(C, TEXT("defenseValue"));
    Card.BoostValue = IntOr(C, TEXT("boostValue"));
    Card.Count = FMath::Max(1, IntOr(C, TEXT("count")));
    List.Total += Card.Count;
    List.Cards.Add(MoveTemp(Card));
  }
  return List;
}
}  // namespace UmDecksGallery

namespace {
FS09CardView UmDgCard(const FS09DeckList& List, const FString& Slug, const TCHAR* Name, int32 Copy) {
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

void UmDgPlace(UWidget* W, const FBox2D& R) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetPosition(R.Min);
    S->SetSize(R.GetSize());
  }
}
}  // namespace

bool UUmDecksGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

TArray<FString> UUmDecksGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    Lines.Add(TEXT("UMGALLERY decks pending canvas=0x0"));
    return Lines;
  }
  BoardNow = Board.ToLower();
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  const FBox2D Field = UmHandGallery::FieldSu(BoardNow, CanvasSu, PxPerSu);
  Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, &Field);
  Layout.bEnglishChips = UmCardMedia::PreferredLang() == TEXT("en");
  // ---- the HB-26 moment (ВР-VS2-HB26-02) ----
  auto Side = [](const TCHAR* Hero, const TCHAR* Slug, const TCHAR* Id) {
    FSide S;
    S.Hero = Hero;
    S.Slug = Slug;
    S.List = UmDecksGallery::LoadList(Slug, Id);
    S.Panel.PlayerId = Id;
    return S;
  };
  if (bSarpedon) {
    Own = Side(TEXT("King Arthur"), TEXT("king-arthur"), TEXT("gallery-own"));
    Opp = Side(TEXT("Medusa"), TEXT("medusa"), TEXT("gallery-opp"));
    Own.Panel.DeckCount = 25;
    for (const TCHAR* N : {TEXT("Noble Sacrifice"), TEXT("Swift Strike"), TEXT("The Holy Grail")}) Own.Panel.Cards.Add(UmDgCard(Own.List, Own.Slug, N, 0));
    Own.Panel.Discard.Add(UmDgCard(Own.List, Own.Slug, TEXT("Momentous Shift"), 0));
    Own.Panel.Discard.Add(UmDgCard(Own.List, Own.Slug, TEXT("Swift Strike"), 1));  // the top (the later attack)
    Opp.Panel.DeckCount = 22;
    Opp.Panel.HandCount = 6;
    Opp.Panel.Discard.Add(UmDgCard(Opp.List, Opp.Slug, TEXT("Dash"), 0));
    Opp.Panel.Discard.Add(UmDgCard(Opp.List, Opp.Slug, TEXT("Regroup"), 0));
  } else {
    Own = Side(TEXT("Medusa"), TEXT("medusa"), TEXT("gallery-own"));
    Opp = Side(TEXT("King Arthur"), TEXT("king-arthur"), TEXT("gallery-opp"));
    Own.Panel.DeckCount = 23;
    Own.Panel.Cards.Add(UmDgCard(Own.List, Own.Slug, TEXT("Gaze of Stone"), 0));
    Own.Panel.Cards.Add(UmDgCard(Own.List, Own.Slug, TEXT("Gaze of Stone"), 1));
    for (const TCHAR* N : {TEXT("Snipe"), TEXT("Clutching Claws"), TEXT("Dash")}) Own.Panel.Cards.Add(UmDgCard(Own.List, Own.Slug, N, 0));
    Own.Panel.Discard.Add(UmDgCard(Own.List, Own.Slug, TEXT("A Momentary Glance"), 0));
    Own.Panel.Discard.Add(UmDgCard(Own.List, Own.Slug, TEXT("Feint"), 0));  // the top (the later defense)
    Opp.Panel.DeckCount = 24;
    Opp.Panel.HandCount = 5;
    Opp.Panel.Discard.Add(UmDgCard(Opp.List, Opp.Slug, TEXT("Swift Strike"), 0));
  }
  Own.Panel.bIsViewer = true;
  Own.Panel.HandCount = Own.Panel.Cards.Num();
  Own.Panel.HandMaxSize = 7;
  // ---- the sheet: the bench K1 frame of the board as the picture, the blocks on the layout ----
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
  // the hand (state own-fan9 only): under the panel, like the GAME slots
  Hand = CreateWidget<UUmHudHand>(this, UUmHudHand::StaticClass());
  if (Hand) {
    Hand->SetSyncLoad(true);
    Hand->SetClockOverrideMs(0.0);
    const FUmHandFrame Frame = FUmHandFrame::FromLayout(Layout, 1.0f);
    Root->AddChildToCanvas(Hand);
    UmDgPlace(Hand, Frame.SlotSu);
    Hand->SetFrame(Frame);
    Hand->SetVisibility(ESlateVisibility::Collapsed);
  }
  Decks = CreateWidget<UUmHudDecks>(this, UUmHudDecks::StaticClass());
  if (Decks) {
    Root->AddChildToCanvas(Decks);
    UmDgPlace(Decks, Layout.Rect(EUmHudBlock::Decks));
    Decks->SetSyncLoad(true);
    FUmDecksFrame F;
    F.bClassS = Layout.bClassS;
    F.PxPerSu = PxPerSu;
    F.RectSu = Layout.Rect(EUmHudBlock::Decks);
    F.bEnglish = Layout.bEnglishChips;
    Decks->SetFrame(F);
  }
  Panel = CreateWidget<UUmHudDeckPanel>(this, UUmHudDeckPanel::StaticClass());
  if (Panel) {
    Root->AddChildToCanvas(Panel);
    UmDgPlace(Panel, Layout.Rect(EUmHudBlock::DeckPanel));
  }
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(Layout.MarginSu, Layout.MarginSu));
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY decks board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s own=%s/%d opp=%s/%d"), *BoardNow,
                            CanvasSu.X, CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"), *Own.Slug,
                            Own.List.Cards.Num(), *Opp.Slug, Opp.List.Cards.Num()));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

void UUmDecksGalleryWidget::ApplyState(int32 State, double TMs) {
  const bool bRu = UmCardMedia::PreferredLang() != TEXT("en");
  // the chips: stale in state 1, an empty own pile in state 9
  FS09PlayerPanel OwnNow = Own.Panel;
  if (State == 1) {
    // the nearest stale line of the same client in run I: Marmoreal host seq 10 «≈24», Sarpedon joiner seq 14 «≈25»
    OwnNow.DeckCount = BoardNow == TEXT("sarpedon") ? 25 : 24;
    OwnNow.bDeckCountStale = true;
  }
  if (State == 9) OwnNow.Discard.Reset();
  if (Decks) Decks->ApplyModel(UmHudDecks::Gather(&OwnNow, Own.Slug));
  // the hand under the panel (state 10): the HB-22 test hand of 9 different Medusa cards
  if (Hand) {
    if (State == 10) {
      FUmHandModel M;
      M.HandMaxSize = 7;
      M.HeroSlug = TEXT("medusa");
      const FS09DeckList Medusa = Own.Slug == TEXT("medusa") ? Own.List : Opp.List;
      int32 I = 0;
      for (const TCHAR* N : {TEXT("Gaze of Stone"), TEXT("Snipe"), TEXT("Clutching Claws"), TEXT("Dash"), TEXT("Hiss and Slither"),
                             TEXT("Regroup"), TEXT("Second Shot"), TEXT("A Momentary Glance"), TEXT("Winged Frenzy")}) {
        FUmHandCardModel C;
        C.Card = UmDgCard(Medusa, TEXT("medusa"), N, I++);
        M.Cards.Add(C);
      }
      Hand->ApplyModel(M);
      Hand->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    } else {
      Hand->SetVisibility(ESlateVisibility::Collapsed);
    }
  }
  if (!Panel) return;
  const bool bPanel = State >= 2 && State != 9;
  const bool bOppSide = State == 5 || State == 6;
  const FSide& S = bOppSide ? Opp : Own;
  FUmDeckPanelFrame F;
  F.bClassS = Layout.bClassS;
  F.PxPerSu = Layout.PxPerSu;
  F.SlotSu = Layout.Rect(EUmHudBlock::DeckPanel);
  FBox2D HandSu(ForceInit);
  if (State == 10 && Hand) {
    const UmHudHand::FRow& Row = Hand->GetRow();
    HandSu = FBox2D(FVector2D(Row.LeftSu, Row.CardTopSu - UmHudHand::CaptionSu), FVector2D(Row.RightSu, Layout.CanvasSu.Y));
  }
  F.BottomSu = UmHudDeckPanel::BottomOver(F.SlotSu, HandSu);
  Panel->SetFrame(F);
  // before gameDeckLists answers (7) or after it failed (8) the client has no list: the model is built without it
  const EUmDeckListState List = State == 7 ? EUmDeckListState::Loading : State == 8 ? EUmDeckListState::Failed : EUmDeckListState::Loaded;
  const FS09DeckPanelModel S09 = FS09DeckPanelModel::Build(bOppSide ? ES09DeckSide::Opponent : ES09DeckSide::Own,
                                                           bOppSide ? Opp.Panel : OwnNow,
                                                           List == EUmDeckListState::Loaded ? &S.List : nullptr);
  Panel->ApplyModel(UmHudDeckPanel::Gather(S09, S.Hero, S.Slug, List, State == 4, bRu));
  if (State == 3 || State == 6) Panel->ScrollToRow(TNumericLimits<int32>::Max());
  if (State == 2 || State == 4 || State == 5) Panel->ScrollToRow(0);
  if (Panel->Skeleton) Panel->Skeleton->SetClockOverrideMs(TMs);
  Panel->ApplyView(bPanel ? 1.0f : 0.0f, bPanel, 1000.0 * State);
}

TArray<FString> UUmDecksGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  if (!Panel || !Decks) return Lines;
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmDecksGallery::StateCount - 1);
  if (State != StateNow) {
    StateNow = State;
    ApplyState(State, TMs);
    if (Label) {
      Label->SetText(FText::FromString(FString::Printf(TEXT("HB-27/28/47 sheet · %s · %s (review tooling, not an acceptance frame)"),
                                                       *BoardNow, UmDecksGallery::StateName(State))));
    }
  }
  // the loader clock: the wait began at the start of the second (the skeleton from + 300 ms)
  const bool bPanel = State >= 2 && State != 9;
  if (Panel->Skeleton) Panel->Skeleton->SetClockOverrideMs(TMs);
  const FString Loader = Panel->ApplyView(bPanel ? 1.0f : 0.0f, bPanel, TMs);
  Lines.Add(FString::Printf(TEXT("UMGALLERY decks board=%s state=%d:%s t=%.0f"), *BoardNow, State, UmDecksGallery::StateName(State), TMs));
  if (!Loader.IsEmpty()) Lines.Add(Loader);
  Decks->CollectShotLines(Lines);
  Panel->CollectShotLines(Lines);
  if (Hand && State == 10) Hand->CollectShotLines(Lines);
  return Lines;
}

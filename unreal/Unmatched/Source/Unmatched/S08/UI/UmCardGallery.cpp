// VS-3 card review sheets - see UmCardGallery.h.
#include "UmCardGallery.h"

#include "UmCardMedia.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace UmCardGallery {
TArray<FS09CardView> LoadDeck(const FString& HeroSlug, TArray<int32>* Copies) {
  TArray<FS09CardView> Out;
  if (Copies) Copies->Reset();
  const FString Path = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S01"), TEXT("content-") + HeroSlug + TEXT(".json")));
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return Out;
  TSharedPtr<FJsonObject> Root;
  if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid()) return Out;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!Root->TryGetArrayField(TEXT("cards"), Cards)) return Out;
  int32 I = 0;
  for (const TSharedPtr<FJsonValue>& V : *Cards) {
    const TSharedPtr<FJsonObject> C = V.IsValid() ? V->AsObject() : nullptr;
    if (!C.IsValid()) continue;
    FS09CardView Card;
    Card.InstanceId = FString::Printf(TEXT("gallery::%s::%d"), *HeroSlug, I++);
    C->TryGetStringField(TEXT("id"), Card.CardId);
    C->TryGetStringField(TEXT("name"), Card.Name);
    C->TryGetStringField(TEXT("nameRu"), Card.NameRu);
    C->TryGetStringField(TEXT("cardType"), Card.CardType);
    C->TryGetStringField(TEXT("bannerName"), Card.BannerName);
    double N = 0.0;
    if (C->TryGetNumberField(TEXT("attackValue"), N)) Card.AttackValue = static_cast<int32>(N);
    if (C->TryGetNumberField(TEXT("defenseValue"), N)) Card.DefenseValue = static_cast<int32>(N);
    if (C->TryGetNumberField(TEXT("boostValue"), N)) {
      Card.BoostValue = static_cast<int32>(N);
      Card.bHasBoostValue = true;
    }
    int32 Count = 1;
    C->TryGetNumberField(TEXT("count"), Count);
    if (Copies) Copies->Add(Count);
    Out.Add(Card);
  }
  return Out;
}
}  // namespace UmCardGallery

namespace {
UTextBlock* UmCgText(UWidgetTree& Tree, const FString& Text, FName ColorToken, FName Font = TEXT("type.caption")) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  T->SetText(FText::FromString(Text));
  T->SetFont(Theme.Font(Font));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(ColorToken)));
  T->SetShadowOffset(FVector2D::ZeroVector);
  return T;
}

const FS09CardView* UmCgFind(const TArray<FS09CardView>& Deck, const TCHAR* Name) {
  return Deck.FindByPredicate([Name](const FS09CardView& C) { return C.Name == Name; });
}
}  // namespace

bool UUmCardsGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("panel.bg.inset")));
    Background->SetPadding(FMargin(16.0f, 12.0f));
    Rows = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Rows"));
    Background->SetContent(Rows);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

UHorizontalBox* UUmCardsGalleryWidget::AddRow(const FString& Title) {
  if (!Title.IsEmpty()) {
    UTextBlock* T = UmCgText(*WidgetTree, Title, TEXT("text.primary"), TEXT("type.tag"));
    if (UVerticalBoxSlot* S = Rows->AddChildToVerticalBox(T)) S->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 2.0f));
  }
  UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
  if (UVerticalBoxSlot* S = Rows->AddChildToVerticalBox(Row)) S->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 6.0f));
  return Row;
}

UUmCardWidget* UUmCardsGalleryWidget::AddCard(UHorizontalBox* Row, const FString& Caption, const FS09CardView& Data,
                                              const FString& Hero, EUmCardShow Show, const FString& Lang, bool bFaceDown,
                                              int32 Legacy) {
  UVerticalBox* Cell = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
  if (UVerticalBoxSlot* S = Cell->AddChildToVerticalBox(UmCgText(*WidgetTree, Caption, TEXT("text.secondary")))) {
    S->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 20.0f));  // room for the chip / drop icon above the card
  }
  UUmCardWidget* CardW = CreateWidget<UUmCardWidget>(this, UUmCardWidget::WidgetClass());
  if (!CardW) return nullptr;
  CardW->SetClockOverrideMs(0.0);
  CardW->SetSyncLoad(true);  // review sheet: no spinner frame
  CardW->SetLegacyForTest(Legacy);
  FUmCardState State;
  State.Show = Show;
  State.HeroSlug = Hero;
  State.Lang = Lang;
  State.bFaceDown = bFaceDown;
  State.PxPerSu = PxPerSuNow;
  CardW->ApplyModel(Data, State);
  Cell->AddChildToVerticalBox(CardW);
  if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Cell)) {
    S->SetPadding(FMargin(0.0f, 0.0f, PageNow <= 8 ? 8.0f : 12.0f, 0.0f));
    S->SetVerticalAlignment(VAlign_Bottom);
  }
  Cards.Add(CardW);
  CellNames.Add(Caption.Replace(TEXT(" "), TEXT("_")));
  return CardW;
}

TArray<FString> UUmCardsGalleryWidget::Build(int32 Page, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Rows) return {TEXT("UMGALLERY cards failed: no rows")};
  Rows->ClearChildren();
  Cards.Reset();
  CellNames.Reset();
  KeepAlive.Reset();
  PageNow = FMath::Clamp(Page, 1, UmCardGallery::PageCount);
  PxPerSuNow = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  const FString KA(TEXT("king-arthur"));
  const FString MED(TEXT("medusa"));
  TArray<int32> KaCopies, MedCopies;
  const TArray<FS09CardView> Arthur = UmCardGallery::LoadDeck(KA, &KaCopies);
  const TArray<FS09CardView> Medusa = UmCardGallery::LoadDeck(MED, &MedCopies);
  auto Pick = [](const TArray<FS09CardView>& Deck, const TCHAR* Name) {
    const FS09CardView* C = UmCgFind(Deck, Name);
    return C ? *C : FS09CardView();
  };
  if (PageNow <= 8) {
    // CP-03 / CP-04: every card of the deck at 150 x 208 / 225 x 312, RU / EN (8 per row)
    const bool bMedusa = PageNow >= 5;
    const bool bEn = ((PageNow - 1) / 2) % 2 == 1;
    const bool bHover = PageNow % 2 == 0;
    const TArray<FS09CardView>& Deck = bMedusa ? Medusa : Arthur;
    const TArray<int32>& Copies = bMedusa ? MedCopies : KaCopies;
    int32 Sum = 0;
    for (int32 C : Copies) Sum += C;
    const FString Hero = bMedusa ? MED : KA;
    UHorizontalBox* Row = nullptr;
    for (int32 I = 0; I < Deck.Num(); ++I) {
      if (I % 8 == 0) {
        Row = AddRow(I == 0 ? FString::Printf(TEXT("%s %s %s - %d cards, %d copies (S01 content API)"), *Hero,
                                              bEn ? TEXT("EN") : TEXT("RU"), bHover ? TEXT("225x312") : TEXT("150x208"),
                                              Deck.Num(), Sum)
                            : FString());
      }
      AddCard(Row, FString::Printf(TEXT("%s x%d"), *UmCardWidget::Slug(Deck[I].Name), Copies.IsValidIndex(I) ? Copies[I] : 1),
              Deck[I], Hero, bHover ? EUmCardShow::Hover : EUmCardShow::Hand, bEn ? TEXT("en") : TEXT("ru"));
    }
  } else if (PageNow <= 10) {
    // CP-05 / CP-06: the back in its five displays
    const FString Hero = PageNow == 9 ? KA : MED;
    UHorizontalBox* Row = AddRow(FString::Printf(TEXT("back:%s - OPP-HAND 48x67, DECKS 32x45, hand / boost 150x208, combat 230x319, inspector"), *Hero));
    FS09CardView Hidden;
    Hidden.InstanceId = TEXT("hidden-0");
    Hidden.bHidden = true;
    AddCard(Row, TEXT("48x67"), Hidden, Hero, EUmCardShow::MiniOpp, TEXT(""), true);
    AddCard(Row, TEXT("32x45"), Hidden, Hero, EUmCardShow::MiniChip, TEXT(""), true);
    AddCard(Row, TEXT("150x208"), Hidden, Hero, EUmCardShow::Hand, TEXT(""), true);
    AddCard(Row, TEXT("230x319"), Hidden, Hero, EUmCardShow::Combat, TEXT(""), true);
    AddCard(Row, TEXT("inspector"), Hidden, Hero, EUmCardShow::Inspector, TEXT(""), true);
  } else if (PageNow == 11) {
    // CP-14: M_UmCardFace at 1 : 1, the hand (0.52) and the chip (0.11); normal and "unplayable"
    UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr, UmCardWidget::MaterialPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
    struct FPair { FString Hero; const TCHAR* Name; };
    for (const FPair& P : {FPair{KA, TEXT("Excalibur")}, FPair{MED, TEXT("Hiss and Slither")}}) {
      const FS09CardView Data = Pick(P.Hero == KA ? Arthur : Medusa, P.Name);
      UHorizontalBox* Row = AddRow(FString::Printf(TEXT("%s:%s RU - M_UmCardFace %s"), *P.Hero, *UmCardWidget::Slug(P.Name),
                                                   Mat ? TEXT("") : TEXT("(material missing)")));
      const FUmCardMediaEntry* E = UmCardMedia::FindCard(P.Hero, UmCardWidget::Slug(P.Name), TEXT("ru"));
      UTexture2D* Tex = E ? UmCardMedia::LoadTexture(*E) : nullptr;
      for (int32 K = 0; K < 2 && Mat && Tex; ++K) {
        UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Mat, this);
        const FVector4 Uv = UmCardWidget::UvRect(*E);
        Mid->SetTextureParameterValue(UmCardWidget::ParamFace, Tex);
        Mid->SetVectorParameterValue(UmCardWidget::ParamUvRect, FLinearColor(Uv.X, Uv.Y, Uv.Z, Uv.W));
        Mid->SetScalarParameterValue(UmCardWidget::ParamDesaturation, K ? UmCardWidget::UnplayableDesaturation : 0.0f);
        Mid->SetScalarParameterValue(UmCardWidget::ParamOpacity, K ? UmCardWidget::UnplayableOpacity : 1.0f);
        KeepAlive.Add(Mid);
        UVerticalBox* Cell = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        Cell->AddChildToVerticalBox(UmCgText(*WidgetTree, K ? TEXT("1.0 unplayable") : TEXT("1.0 normal"), TEXT("text.secondary")));
        UBorder* Under = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
        Under->SetBrushColor(UUmHudTheme::Get().Color(TEXT("card.navy")));
        Under->SetPadding(FMargin(0.0f));
        UImage* Img = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
        FSlateBrush B;
        B.SetResourceObject(Mid);
        B.ImageSize = FVector2D(E->Src.X / PxPerSuNow, E->Src.Y / PxPerSuNow);  // 1 screen px per source px
        Img->SetBrush(B);
        Under->SetContent(Img);
        Cell->AddChildToVerticalBox(Under);
        if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Cell)) {
          S->SetPadding(FMargin(0.0f, 0.0f, 12.0f, 0.0f));
          S->SetVerticalAlignment(VAlign_Bottom);
        }
      }
      for (int32 K = 0; K < 2; ++K) {
        UUmCardWidget* H = AddCard(Row, K ? TEXT("0.52 unplayable") : TEXT("0.52 normal"), Data, P.Hero, EUmCardShow::Hand, TEXT("ru"));
        if (H && K) H->SetPlayable(false, FS09Reason::Make(TEXT("why.defense.only.in.combat")));
      }
      for (int32 K = 0; K < 2; ++K) {
        UUmCardWidget* C = AddCard(Row, K ? TEXT("0.11 unpl.") : TEXT("0.11"), Data, P.Hero, EUmCardShow::MiniChip, TEXT("ru"));
        if (C && K) C->SetPlayable(false, FS09Reason::Make(TEXT("why.defense.only.in.combat")));
      }
    }
  } else if (PageNow == 12) {
    // CP-14: the frame skins stretched 150 x 208 and 230 x 319 (the corner and the edge never stretch), the minis
    const FS09CardView Data = Pick(Arthur, TEXT("Excalibur"));
    for (const EUmCardShow Show : {EUmCardShow::Hand, EUmCardShow::Combat}) {
      UHorizontalBox* Row = AddRow(FString::Printf(TEXT("card.frame.* at %s"), UmCardWidget::ShowName(Show)));
      for (int32 K = 0; K < 6; ++K) {
        static const TCHAR* Names[] = {TEXT("idle"), TEXT("hover"), TEXT("selected"), TEXT("warning"), TEXT("flash"), TEXT("focus")};
        UUmCardWidget* C = AddCard(Row, Names[K], Data, KA, Show, TEXT("ru"));
        if (!C) continue;
        if (K == 1) C->SetFrameOverrideForSheet(TEXT("card.frame.hover"));  // the edge without the 1.5 scale
        if (K == 2) C->SetSelected(true);
        if (K == 3) C->SetDiscardCandidate(true);
        if (K == 4) C->PlayFlash();
        if (K == 5) C->SetFocus(true);
      }
    }
    UHorizontalBox* Mini = AddRow(TEXT("card.frame.mini (mini-idle only, ВР-VS2-CP-06)"));
    FS09CardView Hidden;
    Hidden.InstanceId = TEXT("hidden-0");
    AddCard(Mini, TEXT("48x67 back"), Hidden, KA, EUmCardShow::MiniOpp, TEXT(""), true);
    AddCard(Mini, TEXT("48x67 back"), Hidden, MED, EUmCardShow::MiniOpp, TEXT(""), true);
    AddCard(Mini, TEXT("32x45 back"), Hidden, KA, EUmCardShow::MiniChip, TEXT(""), true);
    AddCard(Mini, TEXT("32x45 face"), Data, KA, EUmCardShow::MiniChip, TEXT("ru"));
    AddCard(Mini, TEXT("32x45 face"), Pick(Medusa, TEXT("Gaze of Stone")), MED, EUmCardShow::MiniChip, TEXT("ru"));
  } else if (PageNow == 13) {
    // CP-14 / CP-15: the inspector - RU 460 x 640 (scan 452 x 627, 1.575 x), EN 408 x 566 (1.6 x)
    UHorizontalBox* Row = AddRow(TEXT("inspector RU 460x640 | EN 408x566 | RU selected"));
    const FS09CardView Data = Pick(Medusa, TEXT("The Hounds of Mighty Zeus"));
    AddCard(Row, TEXT("RU"), Data, MED, EUmCardShow::Inspector, TEXT("ru"));
    AddCard(Row, TEXT("EN"), Data, MED, EUmCardShow::Inspector, TEXT("en"));
    if (UUmCardWidget* C = AddCard(Row, TEXT("RU selected"), Pick(Arthur, TEXT("Excalibur")), KA, EUmCardShow::Inspector, TEXT("ru"))) {
      C->SetSelected(true);
    }
  } else if (PageNow == 14) {
    // CP-15: every display; RU / EN; the fallback (no key) and the rollback look
    const FS09CardView Data = Pick(Arthur, TEXT("Excalibur"));
    UHorizontalBox* Row = AddRow(TEXT("king-arthur:excalibur RU - hand, hover, combat, slot, deckgrid"));
    AddCard(Row, TEXT("hand"), Data, KA, EUmCardShow::Hand, TEXT("ru"));
    AddCard(Row, TEXT("hover"), Data, KA, EUmCardShow::Hover, TEXT("ru"));
    AddCard(Row, TEXT("combat"), Data, KA, EUmCardShow::Combat, TEXT("ru"));
    AddCard(Row, TEXT("slot"), Data, KA, EUmCardShow::Slot, TEXT("ru"));
    AddCard(Row, TEXT("deckgrid"), Data, KA, EUmCardShow::DeckGrid, TEXT("ru"));
    AddCard(Row, TEXT("hand EN"), Data, KA, EUmCardShow::Hand, TEXT("en"));
    AddCard(Row, TEXT("combat EN"), Data, KA, EUmCardShow::Combat, TEXT("en"));
    UHorizontalBox* Row2 = AddRow(TEXT("class S, minis, the fallback (no key, INT-018) and -S08CardArtLegacy"));
    AddCard(Row2, TEXT("classS-hand"), Data, KA, EUmCardShow::ClassSHand, TEXT("ru"));
    AddCard(Row2, TEXT("classS-combat"), Data, KA, EUmCardShow::ClassSCombat, TEXT("ru"));
    AddCard(Row2, TEXT("mini 48x67"), Data, KA, EUmCardShow::MiniOpp, TEXT("ru"));
    AddCard(Row2, TEXT("mini 32x45"), Data, KA, EUmCardShow::MiniChip, TEXT("ru"));
    const FS09CardView Hounds = Pick(Medusa, TEXT("The Hounds of Mighty Zeus"));
    AddCard(Row2, TEXT("fallback (no key)"), Hounds, TEXT(""), EUmCardShow::Hand, TEXT("ru"));
    AddCard(Row2, TEXT("fallback combat"), Pick(Arthur, TEXT("Divine Intervention")), TEXT(""), EUmCardShow::Combat, TEXT("ru"));
    AddCard(Row2, TEXT("legacy face"), Data, KA, EUmCardShow::Hand, TEXT("ru"), false, 1);
    AddCard(Row2, TEXT("legacy back"), Data, KA, EUmCardShow::Hand, TEXT("ru"), true, 1);
  } else if (PageNow == 15) {
    // CP-16: a hand of 7 outside combat - the defense cards unplayable, one new card (the dot appears at t = 0)
    UHorizontalBox* Row = AddRow(TEXT("hand of 7 (King Arthur), own turn outside combat: defense unplayable, Swift Strike new"));
    const TCHAR* Hand[] = {TEXT("Excalibur"), TEXT("Bewilderment"), TEXT("Feint"), TEXT("Prophecy"), TEXT("The Holy Grail"),
                           TEXT("Skirmish"), TEXT("Swift Strike")};
    for (const TCHAR* Name : Hand) {
      const FS09CardView Data = Pick(Arthur, Name);
      UUmCardWidget* C = AddCard(Row, UmCardWidget::Slug(Name), Data, KA, EUmCardShow::Hand, TEXT("ru"));
      if (!C) continue;
      if (Data.CardType == TEXT("DEFENSE")) C->SetPlayable(false, FS09Reason::Make(TEXT("why.defense.only.in.combat")));
      if (FCString::Strcmp(Name, TEXT("Swift Strike")) == 0) C->SetNew(true);
    }
    UHorizontalBox* Why = AddRow(TEXT("why.* of an unplayable card (the HAND owner shows it on hover)"));
    if (Cards.IsValidIndex(1)) {
      if (UHorizontalBoxSlot* S = Why->AddChildToHorizontalBox(UmCgText(*WidgetTree, Cards[1]->GetWhyText().ToString(), TEXT("text.primary"), TEXT("type.body")))) {
        S->SetPadding(FMargin(0.0f));
      }
    }
  } else if (PageNow == 16) {
    // CP-17: hover (tween from 0), selected, selected + hover, focus, lowered + hover; CUE-006 flash
    const FS09CardView Data = Pick(Medusa, TEXT("Gaze of Stone"));
    UHorizontalBox* Row = AddRow(TEXT("medusa:gaze-of-stone - normal, hover, selected, selected+hover, focus, lowered+hover, flash (CUE-006)"));
    AddCard(Row, TEXT("normal"), Data, MED, EUmCardShow::Hand, TEXT("ru"));
    if (UUmCardWidget* C = AddCard(Row, TEXT("hover"), Data, MED, EUmCardShow::Hand, TEXT("ru"))) C->SetHover(true);
    if (UUmCardWidget* C = AddCard(Row, TEXT("selected"), Data, MED, EUmCardShow::Hand, TEXT("ru"))) C->SetSelected(true);
    if (UUmCardWidget* C = AddCard(Row, TEXT("selected+hover"), Data, MED, EUmCardShow::Hand, TEXT("ru"))) {
      C->SetSelected(true);
      C->SetHover(true);
    }
    if (UUmCardWidget* C = AddCard(Row, TEXT("focus"), Data, MED, EUmCardShow::Hand, TEXT("ru"))) C->SetFocus(true);
    if (UUmCardWidget* C = AddCard(Row, TEXT("lowered+hover"), Data, MED, EUmCardShow::Hand, TEXT("ru"))) {
      C->SetLowered(true);
      C->SetHover(true);
    }
    if (UUmCardWidget* C = AddCard(Row, TEXT("flash"), Data, MED, EUmCardShow::Hand, TEXT("ru"))) C->PlayFlash();
  } else if (PageNow == 17) {
    // CP-18: the own boost (flip into the back at t = 0, chip +N after it), the opponent's (back, no number)
    const FS09CardView Own = Pick(Arthur, TEXT("Noble Sacrifice"));
    UHorizontalBox* Row = AddRow(TEXT("boost: own (King Arthur, Noble Sacrifice BOOST 3) | opponent (back, chip without a number) | maneuver (face up)"));
    if (UUmCardWidget* C = AddCard(Row, TEXT("own combat"), Own, KA, EUmCardShow::Hand, TEXT("ru"))) {
      C->SetFaceDown(true);
      C->SetBoostChip(Own.BoostValue);
    }
    FS09CardView Hidden;
    Hidden.InstanceId = TEXT("hidden-1");
    if (UUmCardWidget* C = AddCard(Row, TEXT("opp combat"), Hidden, MED, EUmCardShow::Hand, TEXT(""), true)) {
      C->SetBoostChip(UmCardWidget::HiddenBoost);
    }
    AddCard(Row, TEXT("maneuver (revealed)"), Pick(Medusa, TEXT("Snipe")), MED, EUmCardShow::Slot, TEXT("ru"));
  } else if (PageNow == 18) {
    // CP-19: over the hand limit - every card a candidate, two marked
    UHorizontalBox* Row = AddRow(TEXT("hand over its limit (Medusa): candidates state.warning 2 su, two marked (16 su down, card-drop)"));
    const TCHAR* Hand[] = {TEXT("Gaze of Stone"), TEXT("Hiss and Slither"), TEXT("Snipe"), TEXT("Dash"), TEXT("Feint"),
                           TEXT("Regroup"), TEXT("Winged Frenzy"), TEXT("Clutching Claws")};
    int32 I = 0;
    for (const TCHAR* Name : Hand) {
      UUmCardWidget* C = AddCard(Row, UmCardWidget::Slug(Name), Pick(Medusa, Name), MED, EUmCardShow::Hand, TEXT("ru"));
      if (!C) continue;
      C->SetDiscardCandidate(true);
      if (I == 2 || I == 5) C->SetMarkedForDiscard(true);
      ++I;
    }
  } else {
    // CP-20: the reveal - the attack card at t = 0, the defense card DefenseFlipDelayMs later (started by SetClockMs)
    UHorizontalBox* Row = AddRow(TEXT("reveal CUE-010: attack (King Arthur, Excalibur) flips at 0, defense (Medusa, Hiss and Slither) at +120"));
    FS09CardView Hidden;
    Hidden.InstanceId = TEXT("hidden-a");
    AddCard(Row, TEXT("attack"), Hidden, KA, EUmCardShow::Combat, TEXT("ru"), true);
    Hidden.InstanceId = TEXT("hidden-d");
    AddCard(Row, TEXT("defense"), Hidden, MED, EUmCardShow::Combat, TEXT("ru"), true);
    if (Cards.Num() == 2) {
      const FS09CardView Attack = Pick(Arthur, TEXT("Excalibur"));
      Cards[0]->Flip(true, 1.0f, &Attack);
    }
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY cards page=%d/%d pxPerSu=%.3f canvas=%.0fx%.0f cells=%d"), PageNow,
                            UmCardGallery::PageCount, PxPerSuNow, CanvasSu.X, CanvasSu.Y, Cards.Num()));
  Lines += SetClockMs(0.0f);
  return Lines;
}

TArray<FString> UUmCardsGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  // CP-20: the defense card turns DefenseFlipDelayMs after the attack card (the owner's schedule, simulated here)
  if (PageNow == UmCardGallery::PageCount && Cards.Num() == 2 && TMs >= UmCardWidget::DefenseFlipDelayMs(1.0f) &&
      Cards[1]->IsFaceDown() && !Cards[1]->IsFlipping()) {
    const TArray<FS09CardView> Medusa = UmCardGallery::LoadDeck(TEXT("medusa"));
    const FS09CardView* Def = UmCgFind(Medusa, TEXT("Hiss and Slither"));
    Cards[1]->SetClockOverrideMs(UmCardWidget::DefenseFlipDelayMs(1.0f));
    if (Def) Cards[1]->Flip(true, 1.0f, Def);
  }
  for (int32 I = 0; I < Cards.Num(); ++I) {
    UUmCardWidget* C = Cards[I];
    if (!C) continue;
    C->SetClockOverrideMs(TMs);
    C->Step();
    Lines.Add(FString::Printf(TEXT("UMGALLERY card p%d.%s t=%.0f %s"), PageNow, CellNames.IsValidIndex(I) ? *CellNames[I] : TEXT("?"),
                              TMs, *C->ArtLine()));
  }
  return Lines;
}

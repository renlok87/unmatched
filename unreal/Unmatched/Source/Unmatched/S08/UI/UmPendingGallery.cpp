// VS-4 HB-35 / HB-37 review sheet - see UmPendingGallery.h.
#include "UmPendingGallery.h"

#include "../../S09/S09CardSlot.h"
#include "UmCardMedia.h"
#include "UmCardWidget.h"
#include "UmGameHud.h"
#include "UmHandGallery.h"
#include "UmHudPending.h"
#include "UmHudSourceSlot.h"
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

namespace UmPendingGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {
      TEXT("modal-pick"),    TEXT("modal-order"),   TEXT("choose-one"),    TEXT("number"),        TEXT("compact-move"),
      TEXT("compact-place"), TEXT("compact-target"), TEXT("compact-space"), TEXT("toast"),        TEXT("collapsed"),
      TEXT("discard"),       TEXT("boost"),          TEXT("opp"),           TEXT("after-combat"), TEXT("slot-opp-fly"),
      TEXT("slot-opp-hold"), TEXT("slot-opp-show"),  TEXT("slot-opp-fade"), TEXT("slot-boost"),   TEXT("slot-discard")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}
}  // namespace UmPendingGallery

namespace {
/** The deck of a hero from the S01 capture of the content API (names, nameRu, the text the backend sends - EN). */
TArray<FS09CardView> UmPgDeck(const FString& Hero) {
  TArray<FS09CardView> Out;
  const FString Path = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S01"), TEXT("content-") + Hero + TEXT(".json")));
  FString Text;
  TSharedPtr<FJsonObject> Root;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) ||
      !Root.IsValid() || !Root->TryGetArrayField(TEXT("cards"), Cards)) {
    return Out;
  }
  int32 I = 0;
  for (const TSharedPtr<FJsonValue>& V : *Cards) {
    const TSharedPtr<FJsonObject> C = V.IsValid() ? V->AsObject() : nullptr;
    if (!C.IsValid()) continue;
    FS09CardView Card;
    Card.InstanceId = FString::Printf(TEXT("%s::gallery-%d"), *Hero, I++);
    C->TryGetStringField(TEXT("id"), Card.CardId);
    C->TryGetStringField(TEXT("name"), Card.Name);
    C->TryGetStringField(TEXT("nameRu"), Card.NameRu);
    C->TryGetStringField(TEXT("cardType"), Card.CardType);
    C->TryGetStringField(TEXT("bannerName"), Card.BannerName);
    C->TryGetStringField(TEXT("textEn"), Card.Text);
    double N = 0.0;
    if (C->TryGetNumberField(TEXT("attackValue"), N)) Card.AttackValue = static_cast<int32>(N);
    if (C->TryGetNumberField(TEXT("defenseValue"), N)) Card.DefenseValue = static_cast<int32>(N);
    if (C->TryGetNumberField(TEXT("boostValue"), N)) {
      Card.BoostValue = static_cast<int32>(N);
      Card.bHasBoostValue = true;
    }
    Card.bVisible = true;
    Out.Add(Card);
  }
  return Out;
}

FString UmPgFmt(EUmTable Table, const TCHAR* Key, std::initializer_list<TPair<const TCHAR*, FString>> Args) {
  FFormatNamedArguments A;
  for (const TPair<const TCHAR*, FString>& P : Args) A.Add(P.Key, FText::FromString(P.Value));
  return UmText::Format(Table, Key, A).ToString();
}
}  // namespace

bool UUmPendingGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

FS09CardView UUmPendingGalleryWidget::CardOf(const TCHAR* Hero, const TCHAR* Name) const {
  if (const TArray<FS09CardView>* Deck = Decks.Find(Hero)) {
    for (const FS09CardView& C : *Deck) {
      if (C.Name == Name) return C;
    }
  }
  FS09CardView None;
  None.Name = Name;
  None.InstanceId = FString::Printf(TEXT("%s::%s"), Hero, Name);
  return None;
}

TArray<FString> UUmPendingGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    Lines.Add(TEXT("UMGALLERY pending pending canvas=0x0"));
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
    Pending = CreateWidget<UUmHudPending>(Game, UUmHudPending::WidgetClass());
    SourceSlot = CreateWidget<UUmHudSourceSlot>(Game, UUmHudSourceSlot::WidgetClass());
    if (Pending) {
      Game->SetBlock(EUmGameSlot::Pending, Pending);
      Pending->SetSyncLoad(true);  // the sheet: no loading frame in a shot
    }
    if (SourceSlot) {
      Game->SetBlock(EUmGameSlot::SourceSlot, SourceSlot);
      SourceSlot->SetSyncLoad(true);
      SourceSlot->SetReducedForTest(0);
    }
    Game->ApplyLayout(Layout, TArray<FName>(), false);
  }
  Decks.Add(TEXT("king-arthur"), UmPgDeck(TEXT("king-arthur")));
  Decks.Add(TEXT("medusa"), UmPgDeck(TEXT("medusa")));
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(Layout.MarginSu, CanvasSu.Y - Layout.MarginSu - 20.0));
  }
  StateNow = -1;
  Lines.Add(FString::Printf(TEXT("UMGALLERY pending board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s decks=%d/%d"), *BoardNow,
                            CanvasSu.X, CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"),
                            Decks.FindRef(TEXT("king-arthur")).Num(), Decks.FindRef(TEXT("medusa")).Num()));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

TArray<FString> UUmPendingGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmPendingGallery::StateCount - 1);
  if (State != StateNow) {
    StateNow = State;
    ApplyState(State, Lines);
  }
  return Lines;
}

void UUmPendingGalleryWidget::ApplyState(int32 State, TArray<FString>& Lines) {
  using namespace UmHudPending;
  if (!Pending || !SourceSlot) return;
  const bool bRu = UmCardMedia::PreferredLang() != TEXT("en");
  auto Name = [bRu](const FS09CardView& C) { return bRu && !C.NameRu.IsEmpty() ? C.NameRu : C.Name; };
  // a small monotonic clock per state (the icons keep their clock in float), frozen after the tweens landed
  const double Base = 10000.0 + 2000.0 * State;
  Pending->SetClockOverrideMs(Base);
  SourceSlot->SetClockOverrideMs(Base);
  // ---- the frame of the GAME layout (no STATUS on the sheet: CENTER y) ----
  FUmPendingFrame F;
  F.bClassS = Layout.bClassS;
  F.PxPerSu = Layout.PxPerSu;
  F.CanvasSu = Layout.CanvasSu;
  F.TopSu = static_cast<float>(Layout.Rect(EUmHudBlock::Center).Min.Y);
  F.ModalWidthSu = F.bClassS ? 560.0f : 640.0f;
  F.ModalCapSu = F.bClassS ? 360.0f : (Layout.bTall ? 420.0f : 380.0f);
  F.BandLeftSu = static_cast<float>(Layout.Rect(EUmHudBlock::SourceSlot).Max.X) + 8.0f;
  F.BandRightSu = static_cast<float>(FMath::Min(Layout.Rect(EUmHudBlock::PanelOpp).Min.X, Layout.Rect(EUmHudBlock::OppHand).Min.X)) - 8.0f;
  {
    bool bTop = false;
    const FBox2D Caption = Layout.Rect(EUmHudBlock::HandCaption);
    F.ToastSu = Layout.StackRect(EUmHudBlock::Toast, ToastWidthSu(F.bClassS, Layout.bTall), ToastHSu, 0.0f, 0.0f, TArray<FBox2D>(), bTop,
                                 Caption.bIsValid ? static_cast<float>(Caption.Min.Y) : -1.0f);
  }
  Pending->SetFrame(F);
  FUmSlotFrame SF;
  SF.bClassS = Layout.bClassS;
  SF.PxPerSu = Layout.PxPerSu;
  SF.CardSu = Layout.Rect(EUmHudBlock::SourceSlot);
  SF.OriginSu = UmGameHudSlots::SlotRect(Layout, EUmGameSlot::SourceSlot).Min;
  SourceSlot->SetFrame(SF);
  // ---- the cards (S01 content) ----
  const FS09CardView Prophecy = CardOf(TEXT("king-arthur"), TEXT("Prophecy"));
  const FS09CardView Spirits = CardOf(TEXT("king-arthur"), TEXT("Restless Spirits"));
  const FS09CardView Glance = CardOf(TEXT("medusa"), TEXT("A Momentary Glance"));
  const FS09CardView Hiss = CardOf(TEXT("medusa"), TEXT("Hiss and Slither"));
  const FS09CardView Hounds = CardOf(TEXT("medusa"), TEXT("The Hounds of Mighty Zeus"));
  const FS09CardView Bewilder = CardOf(TEXT("king-arthur"), TEXT("Bewilderment"));
  const FS09CardView Swift = CardOf(TEXT("king-arthur"), TEXT("Swift Strike"));
  const FS09CardView Noble = CardOf(TEXT("king-arthur"), TEXT("Noble Sacrifice"));
  const FS09CardView Grail = CardOf(TEXT("king-arthur"), TEXT("The Holy Grail"));
  auto SlotModel = [](const FS09CardView& Card, ES09SlotRibbon Ribbon, bool bOpp, const TCHAR* Owner, const TCHAR* Slug, int32 Seq) {
    FUmSlotModel M;
    M.bShow = true;
    M.Revision = static_cast<uint32>(Seq);
    M.Seq = Seq;
    M.Phase = EUmSlotPhase::Show;
    M.Card = Card;
    M.bFace = true;
    M.HeroSlug = Slug;
    M.Ribbon = Ribbon;
    M.bOpponent = bOpp;
    M.OwnerName = Owner;
    return M;
  };
  FUmPendingModel M;
  FUmSlotModel S;  // nothing in the slot unless a state puts a card there
  double Freeze = Base + 400.0;
  switch (State) {
    case 0:
    case 1: {
      // Prophecy (King Arthur, Merlin's scheme) DECK_TOP_PICK: the 4 revealed of facts.json revealed_example
      M.View = EUmPendingView::Modal;
      M.Body = State == 0 ? EUmPendingBody::Pick : EUmPendingBody::Order;
      M.Kind = TEXT("DECK_TOP_PICK");
      M.Title = Name(Prophecy);
      M.Text = Prophecy.Text;
      M.HeroSlug = TEXT("king-arthur");
      const TCHAR* Revealed[] = {TEXT("Excalibur"), TEXT("The Aid of Morgana"), TEXT("Aid the Chosen One"), TEXT("Command the Storms")};
      for (int32 I = State == 0 ? 0 : 2; I < 4; ++I) {
        FUmPendingCard C;
        C.Card = CardOf(TEXT("king-arthur"), Revealed[I]);
        C.bMarked = State == 0 && I < 2;
        C.Order = State == 1 ? I - 1 : 0;
        M.Cards.Add(C);
      }
      M.PickNeed = 2;
      M.PickHave = 2;
      M.bConfirm = true;
      M.ConfirmKey = TEXT("hud.number.confirm");
      M.bCollapse = true;
      S = SlotModel(Prophecy, ES09SlotRibbon::Scheme, false, TEXT("King Arthur"), TEXT("king-arthur"), 1);
      break;
    }
    case 2:
      // CHOOSE_ONE: no MVP card (ВР-HB11) - the widget with three options of the server model's shape
      M.View = EUmPendingView::Modal;
      M.Body = EUmPendingBody::Options;
      M.Kind = TEXT("CHOOSE_ONE");
      M.Title = TEXT("CHOOSE_ONE");
      M.Text = TEXT("Choose one:");
      M.Options = {TEXT("Option 1"), TEXT("Option 2"), TEXT("Option 3")};
      M.Selected = 1;
      M.bConfirm = true;
      M.ConfirmKey = TEXT("hud.number.confirm");
      M.bBack = true;
      M.bCollapse = true;
      break;
    case 3:
      M.View = EUmPendingView::Modal;
      M.Body = EUmPendingBody::Number;
      M.Kind = TEXT("NUMBER");
      M.Title = TEXT("NUMBER");
      M.Text = TEXT("Choose a number.");
      M.Number.Min = 1;
      M.Number.Max = 3;
      M.Number.Value = 2;
      M.Number.Result = TEXT("2");
      M.bBack = true;
      M.bCollapse = true;
      break;
    case 4:
      // The Hounds of Mighty Zeus: MOVE the first Harpy of three (sidekick name = the database's «Harpies»)
      M.View = EUmPendingView::Compact;
      M.Kind = TEXT("MOVE");
      M.Title = Name(Hounds);
      M.Icon = FName(TEXT("state-pending-move"));
      M.QueueMore = 2;
      M.Text = UmPgFmt(EUmTable::Ms, TEXT("ms.pending.move"), {{TEXT("fighterName"), TEXT("Harpies")}, {TEXT("n"), TEXT("3")}});
      M.bStay = true;
      M.bCollapse = true;
      break;
    case 5:
      M.View = EUmPendingView::Compact;
      M.Kind = TEXT("PLACE");
      M.Title = Name(Bewilder);
      M.Icon = FName(TEXT("state-pending-place"));
      M.Text = UmPgFmt(EUmTable::Ms, TEXT("ms.pending.place"), {{TEXT("fighterName"), TEXT("Merlin")}});
      M.bDecline = true;
      M.bCollapse = true;
      break;
    case 6:
      M.View = EUmPendingView::Compact;
      M.Kind = TEXT("TARGET_FIGHTER");
      M.Title = Name(Glance);
      M.Text = Glance.Text;
      M.bCollapse = true;
      S = SlotModel(Glance, ES09SlotRibbon::Scheme, false, TEXT("Medusa"), TEXT("medusa"), 2);
      break;
    case 7:
      M.View = EUmPendingView::Compact;
      M.Kind = TEXT("CHOOSE_SPACE");
      M.Title = Name(Spirits);
      M.Icon = FName(TEXT("state-pending-place"));
      M.Text = FirstSentence(Spirits.Text);
      M.bCollapse = true;
      S = SlotModel(Spirits, ES09SlotRibbon::Scheme, false, TEXT("King Arthur"), TEXT("king-arthur"), 3);
      break;
    case 8:
      M.View = EUmPendingView::Toast;
      M.Kind = TEXT("TARGET_FIGHTER");
      M.Title = TEXT("Medusa");
      M.Text = UmPgFmt(EUmTable::Ms, TEXT("ms.pending.remembered"), {{TEXT("choice"), TEXT("King Arthur")}});
      break;
    case 9:
      M.View = EUmPendingView::Collapsed;
      M.Kind = TEXT("DECK_TOP_PICK");
      M.Text = UmPgFmt(EUmTable::Hud, TEXT("hud.pending.collapsed"), {{TEXT("card"), Name(Prophecy)}});
      S = SlotModel(Prophecy, ES09SlotRibbon::Scheme, false, TEXT("King Arthur"), TEXT("king-arthur"), 4);
      break;
    case 10:
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::Discard;
      M.Kind = TEXT("DISCARD_CARDS");
      M.Title = Name(Hiss);
      M.Text = UmPgFmt(EUmTable::Hud, TEXT("hud.pending.discard.count"), {{TEXT("n"), TEXT("1")}, {TEXT("h"), TEXT("1")}});
      M.bConfirm = true;
      M.ConfirmKey = TEXT("hud.number.confirm");
      break;
    case 11:
      M.View = EUmPendingView::Compact;
      M.Compact = EUmPendingCompact::Boost;
      M.Kind = TEXT("ABILITY");
      M.bConfirm = true;
      M.ConfirmKey = TEXT("ms.btn.boost.attack");
      M.bSecondary = true;
      M.SecondaryKey = TEXT("ms.btn.noboost");
      break;
    case 12:
      M.View = EUmPendingView::Opp;
      M.Kind = TEXT("DISCARD_CARDS");
      M.Title = Name(Hiss);
      M.Text = UmText::Get(EUmTable::Why, TEXT("why.wait.opponent.choice")).ToString();
      break;
    case 13:
      M.View = EUmPendingView::AfterCombat;
      M.Kind = TEXT("MOVE");
      M.Title = Name(Swift);
      M.Text = UmText::Get(EUmTable::Hud, TEXT("hud.pending.after.combat")).ToString();
      break;
    case 14:
    case 15:
    case 16:
    case 17: {
      // the opponent's scheme (King Arthur plays Restless Spirits): fly 50 %, hold 50 %, shown with the grey compact,
      // the leave at its middle (75 of 150 ms)
      S = SlotModel(Spirits, ES09SlotRibbon::Scheme, true, TEXT("King Arthur"), TEXT("king-arthur"), 10);
      if (State == 14) {
        S.Phase = EUmSlotPhase::Fly;
        S.FlyT = 0.5f;
        S.FlyFromSu = Layout.Rect(EUmHudBlock::OppHand).GetCenter();
      } else if (State == 15) {
        S.Phase = EUmSlotPhase::Hold;
        S.HoldFrac = 0.5f;
      } else if (State == 16) {
        M.View = EUmPendingView::Opp;
        M.Kind = TEXT("CHOOSE_SPACE");
        M.Title = Name(Spirits);
        M.Text = UmText::Get(EUmTable::Why, TEXT("why.wait.opponent.choice")).ToString();
      }
      break;
    }
    case 18:
      // the opponent's maneuver boost - public after the maneuver (SD-54, ВР-VS4-13): its face with «+N»
      S = SlotModel(Noble, ES09SlotRibbon::Boosted, true, TEXT("King Arthur"), TEXT("king-arthur"), 11);
      S.Boost = Noble.bHasBoostValue ? Noble.BoostValue : 3;
      break;
    case 19:
      S = SlotModel(Grail, ES09SlotRibbon::Discarded, true, TEXT("King Arthur"), TEXT("king-arthur"), 12);
      break;
    default:
      break;
  }
  Pending->ApplyModel(M);
  if (State == 17) {
    // the leave: shown, then the model goes - the widget's own 150 ms fade, frozen at its middle
    SourceSlot->ApplyModel(S);
    FUmSlotModel Gone = S;
    Gone.bShow = false;
    Gone.Phase = EUmSlotPhase::Hidden;
    Gone.Revision = S.Revision + 1;
    SourceSlot->ApplyModel(Gone);
    Freeze = Base + 75.0;
    SourceSlot->SetClockOverrideMs(Freeze);
    SourceSlot->ApplyModel(Gone);
  } else {
    SourceSlot->ApplyModel(S);
  }
  Pending->SetClockOverrideMs(Freeze);
  if (State != 17) {
    // the frozen clock: every tween landed - a card the state left fades out to nothing (the game feeds every frame)
    SourceSlot->SetClockOverrideMs(Freeze);
    SourceSlot->ApplyModel(S);
  }
  if (Label) {
    Label->SetText(FText::FromString(FString::Printf(TEXT("%s · %s · %d"), *BoardNow, UmPendingGallery::StateName(State), State)));
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY pending board=%s state=%d:%s view=%s slot=%s"), *BoardNow, State, UmPendingGallery::StateName(State),
                            M.View == EUmPendingView::Hidden ? TEXT("-") : ViewName(M.View), UmHudSourceSlot::PhaseName(SourceSlot->GetPhase())));
  TArray<FString> Shot;
  Pending->CollectShotLines(Shot);
  SourceSlot->CollectShotLines(Shot);
  Lines.Append(Shot);
}

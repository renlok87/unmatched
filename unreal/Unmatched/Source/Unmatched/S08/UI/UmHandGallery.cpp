// VS-3 HB-24 / HB-25 review sheet - see UmHandGallery.h.
#include "UmHandGallery.h"

#include "UmCardGallery.h"
#include "UmHudTheme.h"
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

namespace UmHandGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("rest-new"), TEXT("hover"), TEXT("selected"), TEXT("unplayable"),
                                           TEXT("boost-maneuver"), TEXT("boost-attack"), TEXT("drop"), TEXT("lowered"),
                                           TEXT("fan-3"), TEXT("fan-7"), TEXT("fan-9"), TEXT("empty"), TEXT("draw")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}

FBox2D FieldSu(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  // the live K1 envelope of every cell at 1080p 100 % (VS-2 exit frames, 'HUD-LAYOUT ... field=(x,y,w,h)')
  const bool bSarpedon = Board.Equals(TEXT("sarpedon"), ESearchCase::IgnoreCase);
  const FBox2D At1080 = bSarpedon ? FBox2D(FVector2D(466.0, 258.0), FVector2D(1461.0, 857.0))
                                  : FBox2D(FVector2D(377.0, 257.0), FVector2D(1542.0, 866.0));
  const double WindowH = CanvasSu.Y * PxPerSu;
  const double WindowW = CanvasSu.X * PxPerSu;
  // the K1 view keeps its horizontal FOV: the board scales with the window width and stays centred vertically
  const double K = WindowW / 1920.0;
  const FVector2D Off(0.0, 0.5 * (WindowH - 1080.0 * K));
  const FBox2D Px(At1080.Min * K + Off, At1080.Max * K + Off);
  return FBox2D(Px.Min / PxPerSu, Px.Max / PxPerSu);
}
}  // namespace UmHandGallery

bool UUmHandGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

TArray<FString> UUmHandGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    // BeginPlay before the first window apply: the sheet is built again on OnUiScaleChanged
    Lines.Add(TEXT("UMGALLERY hand pending canvas=0x0"));
    return Lines;
  }
  BoardNow = Board.ToLower();
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  Medusa = UmCardGallery::LoadDeck(TEXT("medusa"));
  Arthur = UmCardGallery::LoadDeck(TEXT("king-arthur"));
  const FBox2D Field = UmHandGallery::FieldSu(BoardNow, CanvasSu, PxPerSu);
  Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, &Field);
  // the bench K1 frame of the board as the picture under the sheet (the HB-22 backgrounds)
  const FString Rel = bSarpedon ? TEXT("docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png")
                                : TEXT("docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png");
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / Rel);
  // -S08IconGalleryHandPlain: no picture (the sheet in git - no board art, with -S08CardArtLegacy no scans either)
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
  Hand = CreateWidget<UUmHudHand>(this, UUmHudHand::StaticClass());
  if (Hand) {
    Hand->SetSyncLoad(true);
    Hand->SetClockOverrideMs(0.0);
    FUmHandFrame Frame = FUmHandFrame::FromLayout(Layout, 1.0f);
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Hand)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f));
      S->SetPosition(Frame.SlotSu.Min);
      S->SetSize(Frame.SlotSu.GetSize());
    }
    Hand->SetFrame(Frame);
  }
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(Layout.MarginSu, Layout.MarginSu));
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY hand board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s medusa=%d arthur=%d"), *BoardNow,
                            CanvasSu.X, CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"), Medusa.Num(),
                            Arthur.Num()));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

FUmHandModel UUmHandGalleryWidget::ModelFor(int32 State) const {
  FUmHandModel M;
  M.HandMaxSize = 7;
  auto Find = [](const TArray<FS09CardView>& Deck, const TCHAR* Name, int32 Copy) {
    for (const FS09CardView& C : Deck) {
      if (C.Name == Name) {
        FS09CardView Out = C;
        Out.InstanceId = FString::Printf(TEXT("card::%s-%d"), Name, Copy);
        return Out;
      }
    }
    FS09CardView None;
    None.Name = Name;
    None.InstanceId = FString::Printf(TEXT("card::%s-%d"), Name, Copy);
    return None;
  };
  auto Add = [&M](const FS09CardView& C) {
    FUmHandCardModel Card;
    Card.Card = C;
    M.Cards.Add(Card);
  };
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  // the run I hands (HB-22 H6): Marmoreal Medusa 5/7, Sarpedon Medusa 6/7 (order of the frame)
  auto RunHand = [&]() {
    M.HeroSlug = TEXT("medusa");
    if (bSarpedon) {
      for (const TCHAR* N : {TEXT("Clutching Claws"), TEXT("Gaze of Stone"), TEXT("Hiss and Slither"), TEXT("Regroup")}) Add(Find(Medusa, N, 0));
      Add(Find(Medusa, TEXT("Hiss and Slither"), 1));
      FS09CardView New = Find(Medusa, TEXT("Snipe"), 0);
      New.bNew = true;
      Add(New);
    } else {
      Add(Find(Medusa, TEXT("Gaze of Stone"), 0));
      Add(Find(Medusa, TEXT("Gaze of Stone"), 1));
      Add(Find(Medusa, TEXT("Snipe"), 0));
      Add(Find(Medusa, TEXT("Clutching Claws"), 0));
      FS09CardView New = Find(Medusa, TEXT("Dash"), 0);
      New.bNew = true;
      Add(New);
    }
  };
  // «тестовая рука»: 9 different cards of the Medusa deck (HB-22 facts.test_hand)
  auto TestHand = [&](int32 N) {
    M.HeroSlug = TEXT("medusa");
    const TCHAR* Names[] = {TEXT("Gaze of Stone"), TEXT("Snipe"), TEXT("Clutching Claws"), TEXT("Dash"), TEXT("Hiss and Slither"),
                            TEXT("Regroup"), TEXT("Second Shot"), TEXT("A Momentary Glance"), TEXT("Winged Frenzy")};
    for (int32 I = 0; I < N && I < UE_ARRAY_COUNT(Names); ++I) Add(Find(Medusa, Names[I], 0));
  };
  auto ArthurHand = [&]() {
    M.HeroSlug = TEXT("king-arthur");
    for (const TCHAR* N : {TEXT("The Holy Grail"), TEXT("Noble Sacrifice"), TEXT("Swift Strike")}) Add(Find(Arthur, N, 0));
  };
  switch (State) {
    case 0:
    case 1:
      RunHand();
      break;
    case 2:
      RunHand();
      M.Cards[1].bSelected = true;
      break;
    case 3:
      // Medusa chose to attack: the Harpy card is hers no more (why.banner.mismatch), a defense card is no attack
      RunHand();
      for (FUmHandCardModel& C : M.Cards) {
        if (C.Card.CardType.ToUpper() == TEXT("DEFENSE")) C.bPlayable = false;
        if (!UmHudHand::BannerAllows(C.Card.BannerName, TEXT("Medusa"))) {
          C.bPlayable = false;
          C.Reason = FS09Reason::Make(TEXT("why.banner.mismatch")).Arg(TEXT("bannerName"), C.Card.BannerName);
        }
      }
      break;
    case 4:
      RunHand();
      M.Mode = EUmHandMode::Boost;
      M.BoostSlot = EUmHandBoostSlot::Slot;
      M.Cards.Last().bBoostPlaced = true;
      M.Cards.Last().Card.bNew = false;
      break;
    case 5:
      ArthurHand();
      M.Mode = EUmHandMode::Boost;
      M.BoostSlot = EUmHandBoostSlot::Combat;
      M.Cards[1].bBoostPlaced = true;
      M.Cards[2].bSelected = true;
      break;
    case 6:
      TestHand(9);
      M.Mode = EUmHandMode::Discard;
      for (FUmHandCardModel& C : M.Cards) C.bCandidate = true;
      M.Cards[7].bMarked = true;
      M.Cards[8].bMarked = true;
      break;
    case 7:
      RunHand();
      M.Cards[0].bSelected = true;
      M.bLowered = true;
      break;
    case 8:
      ArthurHand();
      break;
    case 9:
      TestHand(7);
      break;
    case 10:
      TestHand(9);
      break;
    case 11:
      M.HeroSlug = TEXT("medusa");
      break;
    case 12:
      RunHand();
      break;
    default:
      break;
  }
  return M;
}

TArray<FString> UUmHandGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  if (!Hand) return Lines;
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmHandGallery::StateCount - 1);
  const double Start = 1000.0 * State;
  if (State != StateNow) {
    StateNow = State;
    Hand->SetClockOverrideMs(Start);
    // the draw: the hand without its last card first, then the card arrives at the start of the second
    if (State == UmHandGallery::StateCount - 1) {
      FUmHandModel Before = ModelFor(State);
      Before.Cards.Pop();
      Hand->ApplyModel(Before);
    }
    Hand->ApplyModel(ModelFor(State));
    Hand->ClearHover();
    if (State == 1) Hand->SetHoverIndex(0);
    if (State == 3) {
      // hover the card with an exact why key (the Harpy banner)
      const FUmHandModel& M = Hand->GetModel();
      for (int32 I = 0; I < M.Cards.Num(); ++I) {
        if (M.Cards[I].Reason.IsSet()) {
          Hand->SetHoverIndex(I);
          break;
        }
      }
    }
    if (Label) {
      Label->SetText(FText::FromString(FString::Printf(TEXT("HB-24/25 sheet · %s · %s (review tooling, not an acceptance frame)"),
                                                       *BoardNow, UmHandGallery::StateName(State))));
    }
  }
  Hand->SetClockOverrideMs(TMs);
  Hand->Step();
  Lines.Add(FString::Printf(TEXT("UMGALLERY hand board=%s state=%d:%s t=%.0f"), *BoardNow, State, UmHandGallery::StateName(State), TMs));
  Hand->CollectShotLines(Lines);
  return Lines;
}

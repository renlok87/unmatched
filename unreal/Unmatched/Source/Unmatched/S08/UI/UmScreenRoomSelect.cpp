// SEL (docs/game-design/select-screens/02-DESIGN.md): the fighting-game look of the ROOM - see UmScreenRoom.h «SEL».
#include "UmHeroShowcase.h"
#include "UmButton.h"
#include "UmCardMedia.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmScreenRoom.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/Image.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"
#include "Misc/PackageName.h"

using namespace UmRoomUi;

namespace {
// ---- the select look's numbers (su, 1080p class L; scaled by K on smaller canvases)
constexpr float SelViewW = 480.0f;  // the niche's figure view, 2:3 like the showcase target
constexpr float SelViewH = 720.0f;
constexpr float SelPlateH = 124.0f;
constexpr float SelTop = 104.0f;
constexpr float SelEdge = 40.0f;
constexpr float SelTileW = 128.0f;
constexpr float SelTileH = 168.0f;
constexpr float SelBoardTileW = 200.0f;
constexpr float SelBoardTileH = 140.0f;
constexpr float SelGap = 16.0f;
constexpr double SelFlashS = 0.30;
constexpr double SelLockBeatS = 1.20;  // review fix 1: «оба выбрали» holds before step 2
const FLinearColor SelP2Text = FLinearColor(FColor::FromHex(TEXT("#A4BECE")));  // review fix 7: P2 small text >= 4.5:1
const TCHAR* const SelRandomId = TEXT("random");

/** A text of the select look: the string table entry when it exists, else the built-in RU / EN text (the keys are
 *  listed in 02-DESIGN.md §10 for the ST_Screens import). */
FText SelT(const TCHAR* Key, const TCHAR* Ru, const TCHAR* En) {
  if (UmText::Has(EUmTable::Screens, Key)) return UmText::Get(EUmTable::Screens, Key);
  const FString Lang = FInternationalization::Get().GetCurrentLanguage()->GetTwoLetterISOLanguageName();
  return FText::FromString(Lang == TEXT("en") ? En : Ru);
}

FLinearColor SelTeam(ES08TeamSlot Slot, float Alpha = 1.0f) {
  FLinearColor C = FLinearColor(S08TeamPalette::ChipColor(Slot));
  C.A = Alpha;
  return C;
}

/** Small text in a team colour: P1 gold reads on navy, P2 takes the lighter tint (review fix 7). */
FLinearColor SelTeamText(ES08TeamSlot Slot) { return Slot == ES08TeamSlot::P1 ? SelTeam(Slot) : SelP2Text; }

ES08TeamSlot SelLookOfSide(int32 OwnSeat, int32 Side) {
  // the absolute team (P1 = seat 0) of the seat drawn on the side (0 = the viewer)
  const int32 Seat = Side == 0 ? OwnSeat : 1 - OwnSeat;
  return Seat == 0 ? ES08TeamSlot::P1 : ES08TeamSlot::P2;
}

UTexture2D* SelLoadTexture(const TCHAR* Path) { return LoadObject<UTexture2D>(nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet); }

/** A texture that may be absent by design (the board preview falls back to the thumbnail): the package is looked up
 *  first, so a missing one is not loaded at all - no LogStreaming «SkipPackage» warning (2026-10-21 recheck). */
UTexture2D* SelLoadOptionalTexture(const FString& PackagePath) {
  if (!FPackageName::DoesPackageExist(PackagePath)) return nullptr;
  return SelLoadTexture(*FString::Printf(TEXT("%s.%s"), *PackagePath, *FPackageName::GetShortName(PackagePath)));
}

double SelNow() { return FPlatformTime::Seconds(); }
}  // namespace

// ------------------------------------------------------------------------------------------------ build

void UUmScreenRoom::SelBuild() {
  bSel = UmShowcase::Enabled();
  if (!bSel || !WidgetTree || !Content || Sel) return;
  UWidgetTree& Tree = *WidgetTree;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Px = UmHudScale::Current().PxPerSu();
  Sel = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Sel")));
  Sel->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  // under the bottom strip and the countdown: insert right after the header panel (index 1 keeps the veil order)
  Content->InsertChildAt(1, Sel);
  auto Border = [&Tree, this](const FString& Name) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    B->SetPadding(FMargin(0.0f));
    B->SetBrush(FSlateNoResource());
    B->SetHorizontalAlignment(HAlign_Center);
    B->SetVerticalAlignment(VAlign_Center);
    Sel->AddChild(B);
    return B;
  };
  auto Text = [&Tree, this](const FString& Name, const TCHAR* Type, const TCHAR* Color) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    Style(T, Type, Color);
    Sel->AddChild(T);
    return T;
  };
  auto Image = [&Tree, this](const FString& Name) {
    UImage* I = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(*Name));
    I->SetVisibility(ESlateVisibility::HitTestInvisible);
    Sel->AddChild(I);
    return I;
  };
  // review target A (04-REVIEW-OPUS.md §C): a dark studio around the niches - the menu scene only glimmers through
  SelVeil = Image(TEXT("SelVeil"));
  {
    FLinearColor V = Theme.Color(TEXT("card.navy"));
    V.A = 0.82f;
    SelVeil->SetColorAndOpacity(V);
  }
  const FSlateBrush* Marble = Theme.SkinFor(TEXT("hud.table.card"), Px);
  for (int32 S = 0; S < 2; ++S) {
    // review target A: the figure stands in a marble-and-bronze niche, a thin team line inside the frame
    Niche[S] = Border(FString::Printf(TEXT("Niche%d"), S));
    if (Marble) {
      Niche[S]->SetBrush(*Marble);
    } else {
      Niche[S]->SetBrush(FSlateRoundedBoxBrush(FLinearColor(0.012f, 0.014f, 0.02f, 1.0f), 10.0f, Theme.Color(TEXT("panel.edge")), 2.0f));
    }
    NicheView[S] = Image(FString::Printf(TEXT("NicheView%d"), S));
    NicheLine[S] = Border(FString::Printf(TEXT("NicheLine%d"), S));
    NicheEmpty[S] = Text(FString::Printf(TEXT("NicheEmpty%d"), S), TEXT("type.display"), TEXT("text.secondary"));
    NicheEmpty[S]->SetJustification(ETextJustify::Center);
    NicheEmpty[S]->SetText(FText::FromString(TEXT("?")));
    NicheHint[S] = Text(FString::Printf(TEXT("NicheHint%d"), S), TEXT("type.body"), TEXT("text.secondary"));
    NicheHint[S]->SetJustification(ETextJustify::Center);
    NicheHint[S]->SetAutoWrapText(true);
    NicheFlash[S] = Border(FString::Printf(TEXT("NicheFlash%d"), S));
    Plate[S] = Border(FString::Printf(TEXT("Plate%d"), S));
    if (Marble) {
      Plate[S]->SetBrush(*Marble);
    } else {
      Plate[S]->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg")), 8.0f, Theme.Color(TEXT("panel.edge")), 2.0f));
    }
    PlateName[S] = Text(FString::Printf(TEXT("PlateName%d"), S), TEXT("type.title"), TEXT("text.primary"));
    PlateNick[S] = Text(FString::Printf(TEXT("PlateNick%d"), S), TEXT("type.body"), TEXT("text.secondary"));
    PlateChip[S] = Border(FString::Printf(TEXT("PlateChip%d"), S));
    PlateChipText[S] = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*FString::Printf(TEXT("PlateChipText%d"), S)));
    Style(PlateChipText[S], TEXT("type.caption"), TEXT("text.primary"));
    PlateChipText[S]->SetJustification(ETextJustify::Center);
    PlateChip[S]->SetContent(PlateChipText[S]);
    PlateSide[S] = Text(FString::Printf(TEXT("PlateSide%d"), S), TEXT("type.caption"), TEXT("text.secondary"));
    PlateSideDisc[S] = Border(FString::Printf(TEXT("PlateSideDisc%d"), S));
    for (UTextBlock* T : {PlateName[S].Get(), PlateNick[S].Get(), PlateSide[S].Get()}) {
      T->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);
      T->SetClipping(EWidgetClipping::ClipToBounds);
    }
  }
  StepTitle = Text(TEXT("StepTitle"), TEXT("type.display"), TEXT("text.primary"));
  StepTitle->SetJustification(ETextJustify::Center);
  StepSub = Text(TEXT("StepSub"), TEXT("type.body"), TEXT("text.secondary"));
  StepSub->SetJustification(ETextJustify::Center);
  VsMedal = Border(TEXT("VsMedal"));
  VsText = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("VsText")));
  Style(VsText, TEXT("type.display"), TEXT("card.cream"));
  VsText->SetJustification(ETextJustify::Center);
  VsText->SetText(FText::FromString(TEXT("VS")));
  VsMedal->SetContent(VsText);
  {
    const FLinearColor Bronze = FLinearColor(FColor::FromHex(TEXT("#8C6B3F")));
    const FLinearColor Gold = FLinearColor(FColor::FromHex(TEXT("#C9A45C")));
    VsMedal->SetBrush(FSlateRoundedBoxBrush(Bronze, 60.0f, Gold, 3.0f));
  }
  InfoCard = Border(TEXT("InfoCard"));
  if (Marble) {
    InfoCard->SetBrush(*Marble);
  } else {
    InfoCard->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg")), 8.0f, Theme.Color(TEXT("panel.edge")), 2.0f));
  }
  InfoName = Text(TEXT("InfoName"), TEXT("type.title"), TEXT("text.primary"));
  InfoStats = Text(TEXT("InfoStats"), TEXT("type.body"), TEXT("text.primary"));
  InfoSide = Text(TEXT("InfoSide"), TEXT("type.body"), TEXT("text.secondary"));
  InfoAbility = Text(TEXT("InfoAbility"), TEXT("type.body"), TEXT("text.secondary"));
  InfoAbility->SetAutoWrapText(true);
  TileRow = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("TileRow")));
  TileRow->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  Sel->AddChild(TileRow);
  // ---- step 2
  PreviewFrame = Border(TEXT("PreviewFrame"));
  PreviewFrame->SetBrush(FSlateRoundedBoxBrush(FLinearColor(0.01f, 0.012f, 0.018f, 1.0f), 10.0f,
                                               FLinearColor(FColor::FromHex(TEXT("#C9A45C"))), 3.0f));
  Preview = Image(TEXT("Preview"));
  PreviewName = Text(TEXT("PreviewName"), TEXT("type.title"), TEXT("text.primary"));
  PreviewName->SetJustification(ETextJustify::Center);
  PreviewHint = Text(TEXT("PreviewHint"), TEXT("type.body"), TEXT("text.secondary"));
  PreviewHint->SetJustification(ETextJustify::Center);
  BoardRow = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("BoardRow")));
  BoardRow->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  Sel->AddChild(BoardRow);
  const TCHAR* const Keys[2] = {TEXT("marmoreal"), TEXT("sarpedon")};
  for (int32 I = 0; I < 3; ++I) {
    UUmSelectTile* T = CreateWidget<UUmSelectTile>(this, UUmSelectTile::StaticClass());
    if (!T) continue;
    BoardRow->AddChild(T);
    T->OnClick = [this, I]() { SelBoardClick(I); };
    T->OnHover = [this, I](bool bOn) { SelBoardHover(I, bOn); };
    BoardTiles.Add(T);
    if (I < 2) {
      BoardThumbs[I] = SelLoadTexture(*FString::Printf(TEXT("/Game/S08/UI/Boards/T_BoardThumb_%s.T_BoardThumb_%s"), Keys[I], Keys[I]));
      BoardPreviews[I] = SelLoadOptionalTexture(FString::Printf(TEXT("/Game/S08/UI/Boards/T_BoardPreview_%s"), Keys[I]));
      if (!BoardPreviews[I]) BoardPreviews[I] = BoardThumbs[I];
    }
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  BackButton = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("BackButton")));
  // a control of the bottom strip: over the strip panel, under the countdown veil
  const int32 VeilAt = CountVeil ? Content->GetChildIndex(CountVeil) : INDEX_NONE;
  if (VeilAt != INDEX_NONE) {
    Content->InsertChildAt(VeilAt, BackButton);
  } else {
    Content->AddChild(BackButton);
  }
  {
    FUmButtonModel M;
    M.Variant = EUmButtonVariant::Normal;
    M.Label = SelT(TEXT("screens.sel.back.hero"), TEXT("‹ Герой"), TEXT("‹ Hero"));
    M.HeightSu = 40.0f;
    M.MinWidthSu = 140.0f;
    BackButton->ApplyModel(M);
  }
  Showcase = AUmHeroShowcase::Get(GetWorld());
  for (int32 S = 0; S < 2; ++S) {
    if (UTextureRenderTarget2D* RT = Showcase.IsValid() ? Showcase->GetTarget(S) : nullptr) {
      FSlateBrush B;
      B.SetResourceObject(RT);
      B.ImageSize = FVector2D(UmShowcase::TargetW, UmShowcase::TargetH);
      B.DrawAs = ESlateBrushDrawType::Image;
      NicheView[S]->SetBrush(B);
    }
  }
  // the legacy blocks never show in the select look
  for (UWidget* W : {static_cast<UWidget*>(Slot0), static_cast<UWidget*>(Slot1), static_cast<UWidget*>(HeroScroll),
                     static_cast<UWidget*>(BoardBlock), static_cast<UWidget*>(BoardTitle), static_cast<UWidget*>(BoardCards),
                     static_cast<UWidget*>(BoardWhy), static_cast<UWidget*>(DeckRow), static_cast<UWidget*>(DeckCount),
                     static_cast<UWidget*>(DeckWhy)}) {
    if (W) W->SetVisibility(ESlateVisibility::Collapsed);
  }
}

// ------------------------------------------------------------------------------------------------ tiles

FString UUmScreenRoom::SelFighterName(const FUmHeroCardModel& H) const { return UmShowcase::FighterForSlug(H.Key, H.Name); }

void UUmScreenRoom::SelSyncTiles() {
  if (!bSel || !TileRow) return;
  const int32 Want = Model.Heroes.Num() + 1;  // + «Случайный»
  while (Tiles.Num() < Want) {
    UUmSelectTile* T = CreateWidget<UUmSelectTile>(this, UUmSelectTile::StaticClass());
    if (!T) break;
    const int32 I = Tiles.Num();
    TileRow->AddChild(T);
    T->OnClick = [this, I]() { SelTileClick(I); };
    T->OnHover = [this, I](bool bOn) { SelTileHover(I, bOn); };
    Tiles.Add(T);
  }
  TilePortraits.SetNum(Model.Heroes.Num());
  TileRegions.SetNum(Model.Heroes.Num());
  for (int32 I = 0; I < Model.Heroes.Num(); ++I) {
    if (TilePortraits[I]) continue;
    const FUmCardMediaEntry* E = UmCardMedia::FindPortrait(Model.Heroes[I].Key.ToString());
    if (!E) continue;
    TilePortraits[I] = UmCardMedia::LoadTexture(*E);
    // the tile picture is ~0.88 wide per high: a head-and-shoulders crop around the registry's face disc, inside the
    // source pixels of the padded texture (uv = src / pad)
    const FVector2f Uv(E->Uv.X > 0.0 ? E->Uv.X : 1.0, E->Uv.Y > 0.0 ? E->Uv.Y : 1.0);
    const float Cx = E->bHasDisc ? E->Disc.X : 0.5f, Cy = E->bHasDisc ? E->Disc.Y : 0.45f;
    const float Hh = 0.86f, Ww = Hh * 0.88f;
    const float X0 = FMath::Clamp(Cx - 0.5f * Ww, 0.0f, 1.0f - Ww);
    const float Y0 = FMath::Clamp(Cy - 0.40f * Hh, 0.0f, 1.0f - Hh);
    TileRegions[I] = FBox2f(FVector2f(X0 * Uv.X, Y0 * Uv.Y), FVector2f((X0 + Ww) * Uv.X, (Y0 + Hh) * Uv.Y));
  }
}

void UUmScreenRoom::SelTileClick(int32 Index) {
  if (Phase != EUmRoomPhase::Room) return;
  if (Index == Model.Heroes.Num()) {  // «Случайный»: one of the free heroes (never the other side's pick, GD-016)
    TArray<int32> Free;
    for (int32 I = 0; I < Model.Heroes.Num(); ++I) {
      const FUmHeroCardModel& H = Model.Heroes[I];
      if (H.State == EUmHeroCardState::Normal && H.bEnabled && H.bDetails) Free.Add(I);
    }
    if (Free.Num() == 0) return;
    Index = Free[FMath::RandRange(0, Free.Num() - 1)];
  }
  SimulatePress(FName(*FString::Printf(TEXT("screens.room.hero.pick.%d"), Index)));
  bForceHeroStep = false;
}

void UUmScreenRoom::SelTileHover(int32 Index, bool bOn) {
  if (bOn) {
    HoverTile = Index;
    Sound(TEXT("UI-HOVER"));
  } else if (HoverTile == Index) {
    HoverTile = INDEX_NONE;
  }
  SelRefresh();
}

void UUmScreenRoom::SelBoardClick(int32 Index) {
  if (Phase != EUmRoomPhase::Room || !Model.bHost || Model.bBusy) return;
  FString Id = Index == 0 ? FString(UmLobby::MarmorealId) : Index == 1 ? FString(UmLobby::SarpedonId) : FString();
  if (Id.IsEmpty()) Id = FMath::RandBool() ? UmLobby::MarmorealId : UmLobby::SarpedonId;  // «Случайное»
  if (Id == Model.BoardId) return;
  Sound(TEXT("UI-SELECT"));
  if (Input.OnBoard) Input.OnBoard(Id);
}

void UUmScreenRoom::SelBoardHover(int32 Index, bool bOn) {
  if (bOn) {
    HoverBoard = Index;
    Sound(TEXT("UI-HOVER"));
  } else if (HoverBoard == Index) {
    HoverBoard = INDEX_NONE;
  }
  SelRefresh();
}

// ------------------------------------------------------------------------------------------------ state

bool UUmScreenRoom::IsBoardStep() const {
  if (!bSel || bForceHeroStep || Model.OwnHeroId.IsEmpty()) return false;
  if (!(Model.bVsAi || Model.bOppHero)) return false;
  return BothPickedSince > 0.0 && SelNow() - BothPickedSince >= SelLockBeatS;
}

int32 UUmScreenRoom::SelHeroIndexForSide(int32 Side) const {
  if (Side == 0) {
    if (!IsBoardStep() && Tiles.IsValidIndex(HoverTile) && HoverTile < Model.Heroes.Num() &&
        Model.Heroes[HoverTile].State != EUmHeroCardState::Taken) {
      return HoverTile;
    }
    return Model.Heroes.IndexOfByPredicate([this](const FUmHeroCardModel& H) { return H.HeroId == Model.OwnHeroId; });
  }
  const FUmRoomSlotModel& Opp = Model.Slots[1 - FMath::Clamp(Model.OwnSeat, 0, 1)];
  if (Opp.HeroName.IsEmpty()) return INDEX_NONE;
  return Model.Heroes.IndexOfByPredicate([&Opp](const FUmHeroCardModel& H) { return H.Key == Opp.HeroKey || H.Name == Opp.HeroName; });
}

const TCHAR* UUmScreenRoom::NicheState(int32 Side) const {
  const int32 Own = FMath::Clamp(Model.OwnSeat, 0, 1);
  const FUmRoomSlotModel& Seat = Model.Slots[Side == 0 ? Own : 1 - Own];
  // the bot's hero is named at the start (bOppHero is true for VS_AI): its niche stays empty until then
  const bool bHero = Side == 0 ? !Model.OwnHeroId.IsEmpty() : !Seat.HeroName.IsEmpty();
  const bool bReady = Side == 0 ? Model.bOwnReady : Model.bOppReady;
  if (bHero && bReady) return TEXT("ready");
  if (bHero) return TEXT("locked");
  if (Side == 0 && SelHeroIndexForSide(0) != INDEX_NONE) return TEXT("hover");
  return TEXT("empty");
}

int32 UUmScreenRoom::GetTileCount() const { return bSel ? FMath::Min(Tiles.Num(), Model.Heroes.Num() + 1) : 0; }
UUmSelectTile* UUmScreenRoom::GetTile(int32 Index) const { return Index >= 0 && Index < GetTileCount() ? Tiles[Index].Get() : nullptr; }
UUmSelectTile* UUmScreenRoom::GetBoardTile(int32 Index) const { return BoardTiles.IsValidIndex(Index) ? BoardTiles[Index].Get() : nullptr; }

FString UUmScreenRoom::GetPreviewBoardId() const {
  if (HoverBoard == 0) return UmLobby::MarmorealId;
  if (HoverBoard == 1) return UmLobby::SarpedonId;
  return Model.BoardId;
}

// ------------------------------------------------------------------------------------------------ refresh

void UUmScreenRoom::SelRefresh() {
  if (!bSel || !Sel) return;
  // the legacy blocks never show in the select look (Refresh shows the deck texts again)
  for (UWidget* W : {static_cast<UWidget*>(Slot0), static_cast<UWidget*>(Slot1), static_cast<UWidget*>(HeroScroll),
                     static_cast<UWidget*>(BoardBlock), static_cast<UWidget*>(BoardTitle), static_cast<UWidget*>(BoardCards),
                     static_cast<UWidget*>(BoardWhy), static_cast<UWidget*>(DeckRow), static_cast<UWidget*>(DeckCount),
                     static_cast<UWidget*>(DeckWhy)}) {
    if (W) W->SetVisibility(ESlateVisibility::Collapsed);
  }
  const bool bBoard = IsBoardStep();
  const int32 Own = FMath::Clamp(Model.OwnSeat, 0, 1);
  // ---- title
  StepTitle->SetText(bBoard ? SelT(TEXT("screens.sel.board.title"), TEXT("ВЫБОР ПОЛЯ"), TEXT("CHOOSE THE BOARD"))
                            : SelT(TEXT("screens.sel.hero.title"), TEXT("ВЫБОР ГЕРОЯ"), TEXT("CHOOSE YOUR HERO")));
  StepSub->SetText(bBoard ? SelT(TEXT("screens.sel.step2"), TEXT("шаг 2 из 2"), TEXT("step 2 of 2"))
                          : SelT(TEXT("screens.sel.step1"), TEXT("шаг 1 из 2"), TEXT("step 1 of 2")));
  // ---- niches and plates
  for (int32 S = 0; S < 2; ++S) {
    const FUmRoomSlotModel& Seat = Model.Slots[S == 0 ? Own : 1 - Own];
    const int32 HI = SelHeroIndexForSide(S);
    const FUmHeroCardModel* H = Model.Heroes.IsValidIndex(HI) ? &Model.Heroes[HI] : nullptr;
    const FString State = NicheState(S);
    const bool bFigure = H != nullptr && (!Showcase.IsValid() || Showcase->HasFigure(S));
    NicheView[S]->SetVisibility(H ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    NicheEmpty[S]->SetVisibility(H ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
    FText Hint;
    if (!H) {
      if (S == 0) {
        Hint = SelT(TEXT("screens.sel.hint.pick"), TEXT("Выберите героя"), TEXT("Pick a hero"));
      } else if (Model.bVsAi) {
        Hint = SelT(TEXT("screens.sel.hint.ai"), TEXT("ИИ выберет героя при старте"), TEXT("The AI picks at the start"));
      } else if (!Model.bOppPresent) {
        Hint = SelT(TEXT("screens.sel.hint.wait"), TEXT("Ждём соперника…"), TEXT("Waiting for an opponent…"));
      } else {
        Hint = SelT(TEXT("screens.sel.hint.opp"), TEXT("Соперник выбирает…"), TEXT("The opponent is choosing…"));
      }
    }
    NicheHint[S]->SetText(Hint);
    NicheHint[S]->SetVisibility(H ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
    (void)bFigure;
    const ES08TeamSlot Look = SelLookOfSide(Own, S);
    PlateName[S]->SetText(H ? FText::FromString(H->Name) : FText::FromString(TEXT("?")));
    FString Nick = Seat.Username;
    if (S == 1 && Model.bVsAi) Nick = UmLobby::AiBotName();  // 2026-10-21 playtest F3e: «Бот» in RU
    if (Nick.IsEmpty()) Nick = TEXT("—");
    PlateNick[S]->SetText(FText::FromString(Nick));
    FText Chip;
    if (State == TEXT("ready")) Chip = SelT(TEXT("screens.sel.chip.ready"), TEXT("ГОТОВ"), TEXT("READY"));
    else if (State == TEXT("locked")) Chip = SelT(TEXT("screens.sel.chip.locked"), TEXT("ВЫБРАН"), TEXT("LOCKED"));
    else Chip = SelT(TEXT("screens.sel.chip.choosing"), TEXT("ВЫБИРАЕТ…"), TEXT("CHOOSING…"));
    PlateChipText[S]->SetText(Chip);
    const bool bLocked = State == TEXT("ready") || State == TEXT("locked");
    PlateChip[S]->SetBrush(FSlateRoundedBoxBrush(bLocked ? SelTeam(Look) : SelTeam(Look, 0.0f), 4.0f, SelTeam(Look), 1.5f));
    PlateChipText[S]->SetColorAndOpacity(FSlateColor(bLocked ? UUmHudTheme::Get().Color(TEXT("card.navy")) : SelTeamText(Look)));
    PlateSide[S]->SetText(H && H->bDetails && !H->SidekickName.IsEmpty()
                              ? FText::FromString(TEXT("+ ") + SidekickLine(H->SidekickName, H->SidekickCount, H->SidekickHp, H->SidekickAttack, true))
                              : FText::GetEmpty());
    // the line inside the niche frame: the team colour (brighter once locked); the flash of the lock-in over it
    NicheLine[S]->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, 4.0f, SelTeam(Look, bLocked ? 1.0f : 0.45f), bLocked ? 3.0f : 1.5f));
    // the sidekick's round token next to its line (Unmatched DE: the sidekick comes with the hero, review fix 2)
    const FName DiscKey = H && H->bDetails && !H->SidekickName.IsEmpty() ? H->SidekickKey : FName();
    if (DiscKey != SideDiscKey[S] && WidgetTree) {
      SideDiscKey[S] = DiscKey;
      if (DiscKey.IsNone()) {
        PlateSideDisc[S]->ClearChildren();
      } else {
        FString Line;
        PlateSideDisc[S]->SetContent(MakeDisc(*WidgetTree, this, DiscKey, H->SidekickName, 30.0f, PxPerSu, 0.0f, SelKeepAlive, &Line, TEXT("room")));
      }
    }
    PlateSideDisc[S]->SetVisibility(DiscKey.IsNone() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  // ---- the hero card: the hovered hero, else the own pick
  {
    const int32 HI = SelHeroIndexForSide(0);
    const FUmHeroCardModel* H = Model.Heroes.IsValidIndex(HI) ? &Model.Heroes[HI] : nullptr;
    InfoName->SetText(H ? FText::FromString(H->Name) : SelT(TEXT("screens.sel.info.none"), TEXT("Наведите на героя"), TEXT("Hover a hero")));
    if (H && H->bDetails) {
      InfoStats->SetText(FText::Format(FText::FromString(TEXT("{0} · {1}")), Stats(H->Hp, H->Move), AttackWord(H->AttackType)));
      InfoSide->SetText(H->SidekickName.IsEmpty()
                            ? FText::GetEmpty()
                            : FText::FromString(TEXT("+ ") + SidekickLine(H->SidekickName, H->SidekickCount, H->SidekickHp, H->SidekickAttack, true)));
      // the whole ability, wrapped at the card width by the layout (review recommended 5: no «…»)
      InfoAbility->SetText(FText::FromString(H->Ability));
    } else {
      InfoStats->SetText(FText::GetEmpty());
      InfoSide->SetText(FText::GetEmpty());
      InfoAbility->SetText(FText::GetEmpty());
    }
  }
  // ---- tiles
  const ES08TeamSlot ViewerLook = SelLookOfSide(Own, 0);
  const FUmRoomSlotModel& OppSeat = Model.Slots[1 - Own];
  for (int32 I = 0; I < GetTileCount(); ++I) {
    FUmSelectTileModel M;
    if (I < Model.Heroes.Num()) {
      const FUmHeroCardModel& H = Model.Heroes[I];
      M.Id = H.HeroId;
      M.Label = H.Name;
      M.Image = TilePortraits.IsValidIndex(I) ? TilePortraits[I].Get() : nullptr;
      if (TileRegions.IsValidIndex(I) && M.Image) M.Region = TileRegions[I];
      const bool bOwnPick = H.HeroId == Model.OwnHeroId;
      const bool bOppPick = !OppSeat.HeroName.IsEmpty() && (H.Key == OppSeat.HeroKey || H.Name == OppSeat.HeroName);
      M.State = bOppPick || H.State == EUmHeroCardState::Taken ? EUmTileState::Taken
                : (!H.bEnabled || Model.bBusy || !H.bDetails) ? EUmTileState::Disabled
                : bOwnPick ? EUmTileState::Picked : EUmTileState::Normal;
      M.bBadge = bOwnPick || bOppPick;
      M.BadgeLook = bOwnPick ? ViewerLook : SelLookOfSide(Own, 1);
      M.BadgeDigit = M.BadgeLook == ES08TeamSlot::P1 ? 1 : 2;
      M.bSelected = bOwnPick;
    } else {
      M.Id = SelRandomId;
      M.Label = SelT(TEXT("screens.sel.random.hero"), TEXT("Случайный"), TEXT("Random")).ToString();
      M.State = Model.bBusy ? EUmTileState::Disabled : EUmTileState::Normal;
    }
    Tiles[I]->Apply(M, FVector2D(SelTileW, SelTileH), ViewerLook);
  }
  // ---- step 2: the preview, the board tiles
  {
    const FString PreviewId = GetPreviewBoardId();
    const int32 PrevIdx = PreviewId == UmLobby::SarpedonId ? 1 : 0;
    if (UTexture2D* Tex = BoardPreviews[PrevIdx]) {
      FSlateBrush B;
      B.SetResourceObject(Tex);
      B.ImageSize = FVector2D(Tex->GetSizeX(), Tex->GetSizeY());
      B.DrawAs = ESlateBrushDrawType::Image;
      Preview->SetBrush(B);
    }
    const FString Name = Model.BoardNames[PrevIdx].IsEmpty() ? FString(PrevIdx == 0 ? UmLobby::MarmorealName() : UmLobby::SarpedonName()) : Model.BoardNames[PrevIdx];
    PreviewName->SetText(FText::FromString(Name));
    FText Hint;
    if (!Model.bHost) {
      Hint = SelT(TEXT("screens.sel.board.host"), TEXT("Поле выбирает хост"), TEXT("The host picks the board"));
    } else if (PreviewId != Model.BoardId) {
      Hint = SelT(TEXT("screens.sel.board.click"), TEXT("Нажмите, чтобы выбрать это поле"), TEXT("Click to pick this board"));
    } else {
      Hint = SelT(TEXT("screens.sel.board.pick"), TEXT("Выберите поле партии"), TEXT("Pick the match board"));
    }
    PreviewHint->SetText(Hint);
    for (int32 I = 0; I < BoardTiles.Num(); ++I) {
      FUmSelectTileModel M;
      if (I < 2) {
        M.Id = I == 0 ? UmLobby::MarmorealId : UmLobby::SarpedonId;
        // 2026-10-21 playtest F3f: the board's own name in the interface language (boardList nameRu / nameEn)
        M.Label = Model.BoardNames[I].IsEmpty() ? (I == 0 ? UmLobby::MarmorealName() : UmLobby::SarpedonName()) : Model.BoardNames[I];
        M.Image = BoardThumbs[I];
        M.bSelected = M.Id == Model.BoardId;
        M.bBadge = M.bSelected;
        M.BadgeLook = SelLookOfSide(Own, Model.bHost ? 0 : 1);
        M.BadgeDigit = M.BadgeLook == ES08TeamSlot::P1 ? 1 : 2;
      } else {
        M.Id = SelRandomId;
        M.Label = SelT(TEXT("screens.sel.random.board"), TEXT("Случайное"), TEXT("Random")).ToString();
      }
      M.State = (!Model.bHost || Model.bBusy || Model.bOwnReady) ? EUmTileState::Disabled : EUmTileState::Normal;
      BoardTiles[I]->Apply(M, FVector2D(SelBoardTileW, SelBoardTileH), ViewerLook);
    }
  }
  // «Колода · N» on the hero card (review recommended 5)
  if (DeckButton && Model.DeckCount > 0) {
    FUmButtonModel M = DeckButton->GetModel();
    FFormatNamedArguments Args;
    Args.Add(TEXT("n"), FText::AsNumber(Model.DeckCount));
    M.Label = FText::Format(SelT(TEXT("screens.sel.deck"), TEXT("Колода · {n}"), TEXT("Deck · {n}")), Args);
    DeckButton->ApplyModel(M);
  }
  // the back button: only in step 2 while the own seat is not ready
  if (BackButton) {
    FUmButtonModel M = BackButton->GetModel();
    M.bEnabled = !Model.bOwnReady && !Model.bBusy;
    BackButton->ApplyModel(M);
  }
}

// ------------------------------------------------------------------------------------------------ layout

void UUmScreenRoom::SelLayout() {
  if (!bSel || !Sel) return;
  const float W = CanvasSu.X, H = CanvasSu.Y;
  const FVector2D O = FrameRectSu().Min;
  // Sel sits at the canvas origin: its children take canvas coordinates; children of Content take them minus O
  auto P = [](UWidget* Wd, float X, float Y, float Ww, float Hh) { Place(Wd, FVector2D(X, Y), FVector2D(Ww, Hh)); };
  auto PC = [&O](UWidget* Wd, float X, float Y, float Ww, float Hh) { Place(Wd, FVector2D(X, Y) - O, FVector2D(Ww, Hh)); };
  const bool bBoard = IsBoardStep();
  // the 16:9 block centred on ultra-wide canvases (the scene fills the sides)
  const float Wr = FMath::Min(W, H * 16.0f / 9.0f);
  const float X0 = 0.5f * (W - Wr);
  // K: the whole look scales with the canvas height (1080 su = 1); the niches shrink in step 2 (§4)
  const float K = FMath::Clamp((H - 200.0f) / 880.0f, 0.45f, 1.0f);
  // narrow canvases (4:3 1440x1080): the niches give way so the centre column keeps >= 620 su (card, strip, preview)
  const float NKw = (Wr - 2.0f * SelEdge * K - 64.0f * K - 620.0f * K) / (2.0f * SelViewW);
  const float NK = FMath::Max(0.3f, FMath::Min(K * (bBoard ? 0.833f : 1.0f), NKw));
  const float VW = SelViewW * NK, VH = SelViewH * NK, PH = SelPlateH * K;
  const float Top = SelTop + (bBoard ? 60.0f * K : 0.0f);
  const float NX[2] = {X0 + SelEdge * K, X0 + Wr - SelEdge * K - VW};
  PC(Sel, 0.0f, 0.0f, W, H);
  Place(SelVeil, FVector2D::ZeroVector, FVector2D(W, H));
  for (int32 S = 0; S < 2; ++S) {
    const float Rim = 14.0f * K;  // the marble frame around the view
    Place(Niche[S], FVector2D(NX[S] - Rim, Top - Rim), FVector2D(VW + 2.0f * Rim, VH + 2.0f * Rim));
    Place(NicheView[S], FVector2D(NX[S], Top), FVector2D(VW, VH));
    Place(NicheLine[S], FVector2D(NX[S] - 3.0f, Top - 3.0f), FVector2D(VW + 6.0f, VH + 6.0f));
    Place(NicheEmpty[S], FVector2D(NX[S], Top + 0.40f * VH - 40.0f), FVector2D(VW, 80.0f));
    Place(NicheHint[S], FVector2D(NX[S] + 24.0f, Top + 0.40f * VH + 48.0f), FVector2D(VW - 48.0f, 60.0f));
    if (NicheHint[S]) NicheHint[S]->SetWrapTextAt(VW - 48.0f);
    Place(NicheFlash[S], FVector2D(NX[S] - 4.0f, Top - 4.0f), FVector2D(VW + 8.0f, VH + 8.0f));
    const float PY = Top + VH + Rim + 6.0f * K;
    Place(Plate[S], FVector2D(NX[S], PY), FVector2D(VW, PH));
    const float Ix = NX[S] + 16.0f;
    const float Iw = VW - 32.0f;
    const float ChipW = 120.0f;
    Place(PlateName[S], FVector2D(Ix, PY + 10.0f * K), FVector2D(Iw - ChipW - 8.0f, 40.0f));
    Place(PlateChip[S], FVector2D(NX[S] + VW - 16.0f - ChipW, PY + 16.0f * K), FVector2D(ChipW, 28.0f));
    Place(PlateNick[S], FVector2D(Ix, PY + 54.0f * K), FVector2D(Iw, 24.0f));
    const bool bDisc = PlateSideDisc[S] && PlateSideDisc[S]->GetVisibility() != ESlateVisibility::Collapsed;
    Place(PlateSideDisc[S], FVector2D(Ix, PY + 80.0f * K), FVector2D(30.0f, 30.0f));
    Place(PlateSide[S], FVector2D(Ix + (bDisc ? 38.0f : 0.0f), PY + 84.0f * K), FVector2D(Iw - 38.0f, 22.0f));
  }
  // ---- the centre column
  const float CX0 = NX[0] + VW + 32.0f * K;
  const float CX1 = NX[1] - 32.0f * K;
  const float CW = FMath::Max(200.0f, CX1 - CX0);
  const float Mid = 0.5f * (CX0 + CX1);
  P(StepTitle, CX0, SelTop, CW, 64.0f);
  P(StepSub, CX0, SelTop + 64.0f, CW, 26.0f);
  // the VS mark only once both heroes stand locked (review E: no VS before anybody picked)
  const bool bBothLocked = !Model.OwnHeroId.IsEmpty() && !Model.Slots[1 - FMath::Clamp(Model.OwnSeat, 0, 1)].HeroName.IsEmpty();
  Vis(VsMedal, !bBoard && bBothLocked);
  Vis(InfoCard, !bBoard);
  for (UWidget* Wd : {static_cast<UWidget*>(InfoName), static_cast<UWidget*>(InfoStats), static_cast<UWidget*>(InfoSide),
                      static_cast<UWidget*>(InfoAbility)}) {
    Vis(Wd, !bBoard);
  }
  Vis(TileRow, !bBoard, true);
  Vis(PreviewFrame, bBoard);
  Vis(Preview, bBoard);
  Vis(PreviewName, bBoard);
  Vis(PreviewHint, bBoard);
  Vis(BoardRow, bBoard, true);
  Vis(BackButton, bBoard, true);
  if (!bBoard) {
    const float Medal = 140.0f * K;
    P(VsMedal, Mid - 0.5f * Medal, SelTop + 96.0f * K, Medal, Medal);
    const float CardW = FMath::Min(CW, 680.0f * K);
    const float CardH = 268.0f * K + 40.0f;
    const float CardX = Mid - 0.5f * CardW;
    const float CardY = SelTop + 248.0f * K;
    P(InfoCard, CardX, CardY, CardW, CardH);
    P(InfoName, CardX + 24.0f, CardY + 16.0f * K, CardW - 48.0f, 40.0f);
    P(InfoStats, CardX + 24.0f, CardY + 64.0f * K, CardW - 48.0f, 24.0f);
    P(InfoSide, CardX + 24.0f, CardY + 94.0f * K, CardW - 48.0f, 24.0f);
    P(InfoAbility, CardX + 24.0f, CardY + 130.0f * K, CardW - 48.0f, CardH - 130.0f * K - 60.0f);
    if (InfoAbility) InfoAbility->SetWrapTextAt(CardW - 48.0f);
    // the strip: as many tiles in a row as fit the column, centred, rows downwards
    const int32 N = GetTileCount();
    const float TW = SelTileW * K, TH = SelTileH * K, G = SelGap * K;
    const int32 PerRow = FMath::Max(1, FMath::FloorToInt((CW + G) / (TW + G)));
    const int32 Rows = FMath::DivideAndRoundUp(FMath::Max(1, N), PerRow);
    const float RowY = CardY + CardH + 40.0f * K;
    P(TileRow, CX0, RowY, CW, Rows * (TH + G));
    for (int32 I = 0; I < N; ++I) {
      const int32 R = I / PerRow, C = I % PerRow;
      const int32 InRow = FMath::Min(PerRow, N - R * PerRow);
      const float RowW = InRow * TW + (InRow - 1) * G;
      Place(Tiles[I], FVector2D(0.5f * (CW - RowW) + C * (TW + G), R * (TH + G)), FVector2D(TW, TH));
      Tiles[I]->Apply(Tiles[I]->GetModel(), FVector2D(TW, TH), SelLookOfSide(FMath::Clamp(Model.OwnSeat, 0, 1), 0));
      Tiles[I]->SetVisibility(ESlateVisibility::Visible);
    }
    for (int32 I = N; I < Tiles.Num(); ++I) Tiles[I]->SetVisibility(ESlateVisibility::Collapsed);
    // the deck button lives on the hero card in this look
    if (DeckButton) {
      const float Bw = 220.0f;
      PC(DeckButton, CardX + CardW - 24.0f - Bw, CardY + CardH - 52.0f, Bw, 40.0f);
      Vis(DeckButton, !Model.OwnHeroId.IsEmpty(), true);
    }
  } else {
    if (DeckButton) Vis(DeckButton, false);
    const float PW = FMath::Min(CW, 800.0f * K);
    const float PHh = PW * 9.0f / 16.0f;
    const float PX = Mid - 0.5f * PW;
    const float PY = SelTop + 104.0f * K;
    P(PreviewFrame, PX - 4.0f, PY - 4.0f, PW + 8.0f, PHh + 8.0f);
    P(Preview, PX, PY, PW, PHh);
    P(PreviewName, CX0, PY + PHh + 16.0f * K, CW, 40.0f);
    P(PreviewHint, CX0, PY + PHh + 58.0f * K, CW, 24.0f);
    const float BW = SelBoardTileW * K, BH = SelBoardTileH * K, G = SelGap * K;
    const int32 N = BoardTiles.Num();
    const float RowW = N * BW + (N - 1) * G;
    const float RowY = PY + PHh + 100.0f * K;
    P(BoardRow, Mid - 0.5f * RowW, RowY, RowW, BH + 8.0f);
    for (int32 I = 0; I < N; ++I) {
      Place(BoardTiles[I], FVector2D(I * (BW + G), 8.0f), FVector2D(BW, BH));
      BoardTiles[I]->Apply(BoardTiles[I]->GetModel(), FVector2D(BW, BH), SelLookOfSide(FMath::Clamp(Model.OwnSeat, 0, 1), 0));
    }
  }
  // the back button next to «Выйти» in the bottom strip
  if (BackButton && bBoard) {
    const FUmRoomLayout L = UmRoom::Layout(CanvasSu, bClassS);
    const float LeaveW = LeaveButton ? FMath::Max(160.0f, MeasureW(FText::FromString(S(TEXT("screens.room.leave")).ToUpper().ToString()), TEXT("type.button")) + 32.0f) : 160.0f;
    PC(BackButton, L.Bottom.X + 16.0f + LeaveW + 16.0f, L.Bottom.Y + 12.0f, 160.0f, 40.0f);
  }
}

// ------------------------------------------------------------------------------------------------ the showcase

void UUmScreenRoom::SelShowcase() {
  if (!bSel) return;
  if (!Showcase.IsValid()) Showcase = AUmHeroShowcase::Get(GetWorld());
  AUmHeroShowcase* SC = Showcase.Get();
  if (!SC) return;
  const bool bOn = IsShown() && GetVisibility() != ESlateVisibility::Collapsed;
  if (!bOn) return;
  SC->RequestActive();
  const int32 Own = FMath::Clamp(Model.OwnSeat, 0, 1);
  for (int32 S = 0; S < 2; ++S) {
    const int32 HI = SelHeroIndexForSide(S);
    const FString Fighter = Model.Heroes.IsValidIndex(HI) ? SelFighterName(Model.Heroes[HI]) : FString();
    SC->SetHero(S, Fighter, SelLookOfSide(Own, S));
  }
  // lock-ins: the own pick and the opponent's pick play the lunge and flash the niche
  const double Now = SelNow();
  const FString OppHero = Model.Slots[1 - Own].HeroName;
  if (Model.OwnHeroId != PrevOwnHero) {
    if (!Model.OwnHeroId.IsEmpty() && HoverTile == INDEX_NONE) {
      SC->PlayLockIn(0);
      FlashUntil[0] = Now + SelFlashS;
      Sound(TEXT("UI-CONFIRM"));
    } else if (!Model.OwnHeroId.IsEmpty()) {
      SC->PlayLockIn(0);
      FlashUntil[0] = Now + SelFlashS;
    }
    PrevOwnHero = Model.OwnHeroId;
    SelRefresh();
  }
  if (OppHero != PrevOppHero) {
    if (!OppHero.IsEmpty()) {
      SC->PlayLockIn(1);
      FlashUntil[1] = Now + SelFlashS;
    }
    PrevOppHero = OppHero;
    SelRefresh();
  }
  // the lock-in beat: both picked -> hold the facing pair with the VS, then open step 2
  const bool bBoth = !Model.OwnHeroId.IsEmpty() && (Model.bVsAi || Model.bOppHero);
  if (!bBoth) {
    BothPickedSince = 0.0;
  } else if (BothPickedSince <= 0.0) {
    BothPickedSince = Now;
  }
  if (IsBoardStep() != bPrevBoardStep) {
    bPrevBoardStep = IsBoardStep();
    if (bPrevBoardStep) Sound(TEXT("UI-PANEL-OPEN"));
    SelRefresh();
    SelLayout();
  }
  for (int32 S = 0; S < 2; ++S) {
    if (!NicheFlash[S]) continue;
    const float A = FlashUntil[S] > Now ? static_cast<float>((FlashUntil[S] - Now) / SelFlashS) : 0.0f;
    if (A > 0.0f) {
      NicheFlash[S]->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, 12.0f,
                                                    FLinearColor(FColor::FromHex(TEXT("#F4D58A"))).CopyWithNewOpacity(A), 6.0f));
      NicheFlash[S]->SetVisibility(ESlateVisibility::HitTestInvisible);
    } else {
      NicheFlash[S]->SetVisibility(ESlateVisibility::Collapsed);
    }
  }
}

void UUmScreenRoom::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  SelShowcase();
}

// VS-2 HB-18 / HB-19 / HB-20: the player panel - see UmHudPlayerPanel.h.
#include "UmHudPlayerPanel.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtLook.h"
#include "../S08IconMotion.h"
#include "../S08TurnPortraitWidget.h"
#include "UmCardMedia.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmPortrait.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "HAL/PlatformTime.h"
#include "Materials/MaterialInstanceDynamic.h"

const TCHAR* const UUmHudPlayerPanel::LocBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_PANEL_LOC");
const TCHAR* const UUmHudPlayerPanel::OppBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_PANEL_OPP");

// ------------------------------------------------------------------------------------------------- rules

namespace UmHudPanel {
FGeom Geometry(bool bClassS, EUmPanelSide Side) {
  FGeom G;
  const bool bOpp = Side == EUmPanelSide::Opp;
  if (!bClassS) {
    // CX-09 L (facts.json rendered_panels, su): 340 x 136
    G.Size = FVector2D(340.0, 136.0);
    G.RingSu = 104.0f;
    G.DiscSu = 80.0f;
    G.RingPos = FVector2D(bOpp ? 232.0 : 4.0, 12.0);
    G.TextX = bOpp ? 212.0f : 128.0f;
    G.NameTop = 7.0f;
    G.StatusTop = 35.0f;
    G.HpTop = 54.0f;
    G.TrackerSu = 32.0f;
    G.TrackerX = bOpp ? 12.0f : 328.0f;
    G.TrackerTop = bOpp ? 46.0f : 50.0f;  // CX-09: the opponent's tracker 4 su up, clear of the sidekick row
    G.bSidekickRow = true;
    G.SidekickTop = 82.0f;
  } else {
    // CX-09 S: 240 x 96, the avatar 64 in a window of 80, the sidekicks in the tooltip
    G.Size = FVector2D(240.0, 96.0);
    G.RingSu = 80.0f;
    G.DiscSu = 64.0f;
    G.RingPos = FVector2D(bOpp ? 156.0 : 4.0, 8.0);
    G.TextX = bOpp ? 148.0f : 92.0f;
    G.NameTop = 7.0f;
    G.StatusTop = 35.0f;
    G.HpTop = 60.0f;
    G.TrackerSu = 24.0f;
    G.TrackerX = bOpp ? 12.0f : 228.0f;
    G.TrackerTop = 58.0f;
    G.bSidekickRow = false;
    G.SidekickTop = 0.0f;
  }
  return G;
}

const TCHAR* StateName(EUmPanelState State) {
  switch (State) {
    case EUmPanelState::Own: return TEXT("own");
    case EUmPanelState::Opp: return TEXT("opp");
    case EUmPanelState::Ai: return TEXT("ai");
    case EUmPanelState::Fallen: return TEXT("fallen");
    default: return TEXT("wait");
  }
}

const TCHAR* ShotId(EUmPanelSide Side) { return Side == EUmPanelSide::Opp ? TEXT("UI-HUD-PANEL-OPP") : TEXT("UI-HUD-PANEL-LOC"); }

FText StatusText(EUmPanelState State) {
  switch (State) {
    case EUmPanelState::Own: return UmText::Get(EUmTable::Hud, TEXT("hud.panel.status.own")).ToUpper();
    case EUmPanelState::Wait: return UmText::Get(EUmTable::Hud, TEXT("hud.panel.status.wait")).ToUpper();
    case EUmPanelState::Ai: return UmText::Get(EUmTable::Hud, TEXT("hud.opp.thinking")).ToUpper();
    case EUmPanelState::Fallen: return UmText::Get(EUmTable::Hud, TEXT("hud.panel.fallen")).ToUpper();
    default: return FText::GetEmpty();  // ВР-VS2-CX09-07: their turn has no status word of its own
  }
}

FName StatusColorToken(EUmPanelState State) {
  return State == EUmPanelState::Own ? FName(TEXT("turn.flash.yellow")) : FName(TEXT("text.secondary"));
}

FName NameFontToken(const FString& Name) {
  return Name.Len() > NameMaxChars ? FName(TEXT("type.button")) : FName(TEXT("type.heading"));
}

FText HpText(int32 Hp, int32 MaxHp) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("hp"), FText::AsNumber(FMath::Max(Hp, 0)));
  if (MaxHp <= 0) return FText::AsNumber(FMath::Max(Hp, 0));
  Args.Add(TEXT("max"), FText::AsNumber(MaxHp));
  return UmText::Format(EUmTable::Hud, TEXT("hud.panel.hp"), Args);
}

FText SidekickLine(const FUmSidekickView& S) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("name"), FText::FromString(S.Name));  // data, not a string table
  Args.Add(TEXT("hp"), FText::AsNumber(FMath::Max(S.Hp, 0)));
  Args.Add(TEXT("max"), FText::AsNumber(FMath::Max(S.MaxHp, 0)));
  return UmText::Format(EUmTable::Hud, TEXT("hud.panel.sidekick"), Args);
}

float RingSmoulder(bool bClassS) {
  return UUmHudTheme::Get().Alpha(bClassS ? FName(TEXT("ring.smoulder.s")) : FName(TEXT("ring.smoulder")));
}
}  // namespace UmHudPanel

// ------------------------------------------------------------------------------------------------- tree

namespace {
template <typename T>
T* UmPanelMake(UWidgetTree& Tree, const TCHAR* Name, UClass* Class = nullptr) {
  return Tree.ConstructWidget<T>(Class ? Class : T::StaticClass(), FName(Name));
}

template <typename T>
T* UmPanelFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmPanelRowSlot(UWidget* Widget, const FMargin& Padding) {
  if (UHorizontalBoxSlot* RowSlot = Cast<UHorizontalBoxSlot>(Widget ? Widget->Slot : nullptr)) {
    RowSlot->SetPadding(Padding);
    RowSlot->SetVerticalAlignment(VAlign_Center);
  }
}

void UmPanelPlace(UWidget* Widget, const FVector2D& Pos, bool bRightAligned, const FVector2D& Size = FVector2D::ZeroVector) {
  UCanvasPanelSlot* CanvasSlot = Cast<UCanvasPanelSlot>(Widget ? Widget->Slot : nullptr);
  if (!CanvasSlot) return;
  CanvasSlot->SetAnchors(FAnchors(0.0f, 0.0f));
  CanvasSlot->SetAlignment(FVector2D(bRightAligned ? 1.0 : 0.0, 0.0));
  CanvasSlot->SetPosition(Pos);
  const bool bAuto = Size.IsZero();
  CanvasSlot->SetAutoSize(bAuto);
  if (!bAuto) CanvasSlot->SetSize(Size);
}

FSlateBrush UmDiscBrush(const FLinearColor& Color, float Su) {
  return FSlateRoundedBoxBrush(Color, 0.5f * Su, FVector2D(Su, Su));
}
}  // namespace

bool UUmHudPlayerPanel::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, EUmPanelSide InSide, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bOpp = InSide == EUmPanelSide::Opp;
  UBorder* PanelW = UmPanelMake<UBorder>(Tree, TEXT("Panel"));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel"))) PanelW->SetBrush(*Skin);
  PanelW->SetPadding(FMargin(0.0f));
  PanelW->SetHorizontalAlignment(HAlign_Fill);
  PanelW->SetVerticalAlignment(VAlign_Fill);
  PanelW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(PanelW, nullptr)) return Fail(TEXT("Panel"));
  UCanvasPanel* CanvasW = UmPanelMake<UCanvasPanel>(Tree, TEXT("Canvas"));
  if (!Attach(CanvasW, PanelW)) return Fail(TEXT("Canvas"));
  // the circle: WBP_UmPortrait when it exists (CP-08), its own plate and text column collapse in panel mode
  UClass* PortraitClass = UmGameHudSlots::WbpOrNative(US08TurnPortraitWidget::StaticClass(), UmPortrait::WidgetBlueprintPath);
  US08TurnPortraitWidget* PortraitW = UmPanelMake<US08TurnPortraitWidget>(Tree, TEXT("Portrait"), PortraitClass);
  if (!Attach(PortraitW, CanvasW)) return Fail(TEXT("Portrait"));
  UTextBlock* Name = UmPanelMake<UTextBlock>(Tree, TEXT("NameText"));
  Name->SetFont(Theme.Font(TEXT("type.heading")));
  Name->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  Name->SetJustification(bOpp ? ETextJustify::Right : ETextJustify::Left);
  if (!Attach(Name, CanvasW)) return Fail(TEXT("NameText"));
  UHorizontalBox* Status = UmPanelMake<UHorizontalBox>(Tree, TEXT("StatusRow"));
  if (!Attach(Status, CanvasW)) return Fail(TEXT("StatusRow"));
  UImage* Dot = UmPanelMake<UImage>(Tree, TEXT("PulseDot"));
  Dot->SetBrush(UmDiscBrush(Theme.Color(TEXT("text.secondary")), UmHudPanel::DotSu));
  Dot->SetDesiredSizeOverride(FVector2D(UmHudPanel::DotSu, UmHudPanel::DotSu));
  Dot->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Dot, Status)) return Fail(TEXT("PulseDot"));
  UmPanelRowSlot(Dot, FMargin(0.0f, 0.0f, UmHudPanel::DotGapSu, 0.0f));
  UTextBlock* StatusW = UmPanelMake<UTextBlock>(Tree, TEXT("StatusText"));
  StatusW->SetFont(Theme.Font(TEXT("type.tag")));
  StatusW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  if (!Attach(StatusW, Status)) return Fail(TEXT("StatusText"));
  UmPanelRowSlot(StatusW, FMargin(0.0f));
  UHorizontalBox* Hp = UmPanelMake<UHorizontalBox>(Tree, TEXT("HpRow"));
  if (!Attach(Hp, CanvasW)) return Fail(TEXT("HpRow"));
  US08AnimatedIconWidget* Heart = UmPanelMake<US08AnimatedIconWidget>(Tree, TEXT("HeartIcon"));
  if (!Attach(Heart, Hp)) return Fail(TEXT("HeartIcon"));
  UmPanelRowSlot(Heart, FMargin(0.0f, 0.0f, 4.0f, 0.0f));  // CX-09: heart 128..152, the number from 156
  UTextBlock* HpW = UmPanelMake<UTextBlock>(Tree, TEXT("HpText"));
  HpW->SetFont(Theme.Font(TEXT("type.button")));
  HpW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  if (!Attach(HpW, Hp)) return Fail(TEXT("HpText"));
  UmPanelRowSlot(HpW, FMargin(0.0f));
  UHorizontalBox* Tracker = UmPanelMake<UHorizontalBox>(Tree, TEXT("TrackerRow"));
  if (!Attach(Tracker, CanvasW)) return Fail(TEXT("TrackerRow"));
  UHorizontalBox* Sidekicks = UmPanelMake<UHorizontalBox>(Tree, TEXT("SidekickRow"));
  if (!Attach(Sidekicks, CanvasW)) return Fail(TEXT("SidekickRow"));
  // the places of class L (ApplyGeometry moves them for the class of the window)
  const UmHudPanel::FGeom G = UmHudPanel::Geometry(false, InSide);
  UmPanelPlace(PortraitW, G.RingPos, false, FVector2D(G.RingSu, G.RingSu));
  UmPanelPlace(Name, FVector2D(G.TextX, G.NameTop), bOpp);
  UmPanelPlace(Status, FVector2D(G.TextX, G.StatusTop), bOpp);
  UmPanelPlace(Hp, FVector2D(G.TextX, G.HpTop), bOpp);
  UmPanelPlace(Tracker, FVector2D(G.TrackerX, G.TrackerTop), !bOpp);
  UmPanelPlace(Sidekicks, FVector2D(G.TextX, G.SidekickTop), bOpp);
  return true;
}

UClass* UUmHudPlayerPanel::WidgetClass(EUmPanelSide InSide) {
  return UmGameHudSlots::WbpOrNative(UUmHudPlayerPanel::StaticClass(),
                                     InSide == EUmPanelSide::Opp ? OppBlueprintPath : LocBlueprintPath);
}

void UUmHudPlayerPanel::BindParts() {
  UWidgetTree* Tree = WidgetTree;
  Panel = UmPanelFind<UBorder>(Tree, TEXT("Panel"));
  Canvas = UmPanelFind<UCanvasPanel>(Tree, TEXT("Canvas"));
  Portrait = UmPanelFind<US08TurnPortraitWidget>(Tree, TEXT("Portrait"));
  NameText = UmPanelFind<UTextBlock>(Tree, TEXT("NameText"));
  StatusRow = UmPanelFind<UHorizontalBox>(Tree, TEXT("StatusRow"));
  PulseDot = UmPanelFind<UImage>(Tree, TEXT("PulseDot"));
  StatusText = UmPanelFind<UTextBlock>(Tree, TEXT("StatusText"));
  HpRow = UmPanelFind<UHorizontalBox>(Tree, TEXT("HpRow"));
  HeartIcon = UmPanelFind<US08AnimatedIconWidget>(Tree, TEXT("HeartIcon"));
  HpText = UmPanelFind<UTextBlock>(Tree, TEXT("HpText"));
  TrackerRow = UmPanelFind<UHorizontalBox>(Tree, TEXT("TrackerRow"));
  SidekickRow = UmPanelFind<UHorizontalBox>(Tree, TEXT("SidekickRow"));
}

bool UUmHudPlayerPanel::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree) {
    if (!WidgetTree->RootWidget) {
      FString Error;
      UWidgetTree* Tree = WidgetTree;
      bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
        if (!Parent) {
          Tree->RootWidget = Child;
          return true;
        }
        return Parent->AddChild(Child) != nullptr;
      }, EUmPanelSide::Own, &Error);
      if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD panel default tree: %s"), *Error);
    }
    BindParts();
    // the theme font is the default composite font (no font object): a WBP does not keep it - every load takes it again
    ApplyFonts();
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  }
  return bFirst;
}

bool UUmHudPlayerPanel::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Panel) Missing.Add(TEXT("Panel"));
  if (!Canvas) Missing.Add(TEXT("Canvas"));
  if (!Portrait) Missing.Add(TEXT("Portrait"));
  if (!NameText) Missing.Add(TEXT("NameText"));
  if (!StatusRow) Missing.Add(TEXT("StatusRow"));
  if (!PulseDot) Missing.Add(TEXT("PulseDot"));
  if (!StatusText) Missing.Add(TEXT("StatusText"));
  if (!HpRow) Missing.Add(TEXT("HpRow"));
  if (!HeartIcon) Missing.Add(TEXT("HeartIcon"));
  if (!HpText) Missing.Add(TEXT("HpText"));
  if (!TrackerRow) Missing.Add(TEXT("TrackerRow"));
  if (!SidekickRow) Missing.Add(TEXT("SidekickRow"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudPlayerPanel::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudPlayerPanel::ApplyFonts() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (NameText) NameText->SetFont(Theme.Font(UmHudPanel::NameFontToken(Model.HeroName)));
  if (StatusText) StatusText->SetFont(Theme.Font(TEXT("type.tag")));
  if (HpText) HpText->SetFont(Theme.Font(TEXT("type.button")));
}

void UUmHudPlayerPanel::Setup(EUmPanelSide InSide, const FS08TurnHudLook& Look, const FLinearColor& TeamColor) {
  Side = InSide;
  if (Portrait) {
    Portrait->AttachToPanel(TrackerRow, HeartIcon);
    Portrait->Setup(Side == EUmPanelSide::Opp, Look, TeamColor);
    Portrait->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  if (TrackerRow) TrackerRow->SetVisibility(ESlateVisibility::HitTestInvisible);
  const bool bOpp = Side == EUmPanelSide::Opp;
  if (NameText) NameText->SetJustification(bOpp ? ETextJustify::Right : ETextJustify::Left);
  bGeometryApplied = false;
  ApplyGeometry();
}

void UUmHudPlayerPanel::ApplyGeometry() {
  const bool bClassS = Model.bClassS;
  const float PxPerSu = bHasModel ? Model.PxPerSu : 1.0f;
  if (bGeometryApplied && bClassS == bAppliedClassS && FMath::IsNearlyEqual(PxPerSu, AppliedPxPerSu)) return;
  bGeometryApplied = true;
  bAppliedClassS = bClassS;
  AppliedPxPerSu = PxPerSu;
  const bool bOpp = Side == EUmPanelSide::Opp;
  const UmHudPanel::FGeom G = UmHudPanel::Geometry(bClassS, Side);
  // HB-10: the x2 plate from 150 % (DPI x UI scale)
  if (Panel) {
    if (const FSlateBrush* Skin = UUmHudTheme::Get().SkinFor(TEXT("panel"), PxPerSu)) Panel->SetBrush(*Skin);
  }
  UmPanelPlace(Portrait, G.RingPos, false, FVector2D(G.RingSu, G.RingSu));
  UmPanelPlace(NameText, FVector2D(G.TextX, G.NameTop), bOpp);
  UmPanelPlace(StatusRow, FVector2D(G.TextX, G.StatusTop), bOpp);
  UmPanelPlace(HpRow, FVector2D(G.TextX, G.HpTop), bOpp);
  UmPanelPlace(TrackerRow, FVector2D(G.TrackerX, G.TrackerTop), !bOpp);
  UmPanelPlace(SidekickRow, FVector2D(G.TextX, G.SidekickTop), bOpp);
  if (Portrait) {
    Portrait->SetPanelGeometry(G.RingSu, G.DiscSu, G.TrackerSu);
    Portrait->SetRingSmoulder(UmHudPanel::RingSmoulder(bClassS));  // ВР-43: L 0.35, S 0.55
  }
  if (SidekickRow) SidekickRow->SetVisibility(G.bSidekickRow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
}

// ------------------------------------------------------------------------------------------------- model

UWidget* UUmHudPlayerPanel::MakeMiniPortrait(const FUmSidekickView& S) {
  // VS-2 CP-10 / CP-12: the sidekick's avatar in the circle of the accepted CP-07 crop (one picture for the three
  // harpies), saturation 0 when fallen (04 §2.2: the plate stays); no PNG -> the monogram / the harpy's digit;
  // -S08PortraitLegacy -> the fallback as the hero's circle (ВР-CP08)
  FUmPortraitDiscSpec Spec;
  Spec.Key = S.Key;
  Spec.Name = S.Name;
  Spec.Number = S.Number;
  Spec.ShowSu = UmHudPanel::SidekickSu;
  Spec.PxPerSu = Model.PxPerSu;
  Spec.State = S.bFallen ? EUmPortraitState::Fallen : EUmPortraitState::Avatar;
  Spec.bLegacy = Portrait ? Portrait->IsPortraitLegacy() : !S08ArtLook::PortraitAvatars();
  FUmPortraitShown& Shown = MiniShown.AddDefaulted_GetRef();
  return UmPortrait::MakeDisc(*WidgetTree, this, Spec, Shown, KeepAlive);
}

void UUmHudPlayerPanel::CollectPortraitLines(TArray<FString>& Out) const {
  if (!UmGameHudSlots::ShownByProperty(this) || !bHasModel || Model.bClassS) return;
  const TCHAR* SideName = Side == EUmPanelSide::Opp ? TEXT("opp") : TEXT("own");
  for (const FUmPortraitShown& Shown : MiniShown) Out.Add(Shown.Line(TEXT("panel"), SideName));
}

UWidget* UUmHudPlayerPanel::MakeFallenHeart() {
  US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
  if (!Icon || !Icon->SetIcon(FName(FS08TurnHudLook::FallenHeartIcon), UmHudPanel::HeartSu, 24)) return nullptr;
  Icon->SetDisplaySizeSu(UmHudPanel::HeartSu);
  Icon->ShowAtRest();
  return Icon;
}

void UUmHudPlayerPanel::RebuildSidekicks() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bOpp = Side == EUmPanelSide::Opp;
  SidekickItems = 0;
  TooltipRows = 0;
  KeepAlive.Reset();
  MiniShown.Reset();
  if (SidekickRow) SidekickRow->ClearChildren();
  SidekickTip = nullptr;
  SetToolTip(nullptr);
  if (Model.Sidekicks.Num() == 0 || !WidgetTree) return;
  if (!Model.bClassS) {
    // ---- L: the row (CX-09): numbered (the harpies, ВР-72) 64 su apart; a named one (Merlin) with its name ----
    const int32 N = Model.Sidekicks.Num();
    for (int32 I = 0; I < N; ++I) {
      const FUmSidekickView& S = Model.Sidekicks[I];
      UOverlay* Item = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass());
      if (S.Number > 0) {
        UVerticalBox* Column = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        // the mini portrait with the number disc in its lower right corner (+21, +20)
        USizeBox* StackBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        StackBox->SetWidthOverride(UmHudPanel::SidekickSu + 3.0f);
        StackBox->SetHeightOverride(UmHudPanel::SidekickSu + 2.0f);
        UOverlay* Stack = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass());
        StackBox->SetContent(Stack);
        if (UOverlaySlot* P = Stack->AddChildToOverlay(MakeMiniPortrait(S))) {
          P->SetHorizontalAlignment(HAlign_Left);
          P->SetVerticalAlignment(VAlign_Top);
        }
        // CP-12 / 02 §6.5: the number badge (card.navy 14 su + mark.keyline, the digit card.cream as runtime text) on
        // the avatar; the fallback circle is the digit itself (ВР-CP09) - no second digit (ВР-VS2-66)
        if (MiniShown.Num() && MiniShown.Last().IsAvatar()) {
          if (UOverlaySlot* X = Stack->AddChildToOverlay(UmPortrait::MakeNumberBadge(*WidgetTree, S.Number))) {
            X->SetHorizontalAlignment(HAlign_Left);
            X->SetVerticalAlignment(VAlign_Top);
            X->SetPadding(FMargin(21.0f, 20.0f, 0.0f, 0.0f));  // CX-09: the lower right corner, over the circle's edge
          }
        }
        Column->AddChildToVerticalBox(StackBox);
        UTextBlock* Hp = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
        Hp->SetFont(Theme.Font(TEXT("type.tag")));
        Hp->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
        Hp->SetText(UmHudPanel::HpText(S.Hp, S.MaxHp));
        if (UVerticalBoxSlot* H = Column->AddChildToVerticalBox(Hp)) H->SetPadding(FMargin(0.0f, -2.0f, 0.0f, 0.0f));
        Item->AddChildToOverlay(Column);
        if (S.bFallen) {
          // 04 §2.2: the fallen heart 24 su beside the grey mini portrait (CX-09: x +34, y +4)
          if (UWidget* Heart = MakeFallenHeart()) {
            if (UOverlaySlot* H = Item->AddChildToOverlay(Heart)) {
              H->SetHorizontalAlignment(HAlign_Left);
              H->SetVerticalAlignment(VAlign_Top);
              H->SetPadding(FMargin(UmHudPanel::SidekickSu + 2.0f, 4.0f, 0.0f, 0.0f));
            }
          }
        }
        // the items 64 su apart; the last one only as wide as its content (the row's edge, PANEL-OPP right 212)
        USizeBox* Cell = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        Cell->SetWidthOverride(I + 1 < N ? UmHudPanel::SidekickStepSu : UmHudPanel::SidekickSu + 3.0f);
        Cell->SetContent(Item);
        if (UHorizontalBoxSlot* C = SidekickRow->AddChildToHorizontalBox(Cell)) C->SetVerticalAlignment(VAlign_Top);
      } else {
        // a named sidekick: [mini portrait] 12 su [name / hp]
        UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
        UVerticalBox* Text = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        for (int32 Line = 0; Line < 2; ++Line) {
          UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
          T->SetFont(Theme.Font(TEXT("type.tag")));
          T->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
          T->SetJustification(bOpp ? ETextJustify::Right : ETextJustify::Left);
          T->SetText(Line == 0 ? FText::FromString(S.Name) : UmHudPanel::HpText(S.Hp, S.MaxHp));
          if (UVerticalBoxSlot* TS = Text->AddChildToVerticalBox(T)) {
            TS->SetHorizontalAlignment(bOpp ? HAlign_Right : HAlign_Left);
            TS->SetPadding(FMargin(0.0f, Line == 0 ? 2.0f : 4.0f, 0.0f, 0.0f));
          }
        }
        UWidget* Mini = MakeMiniPortrait(S);
        UWidget* Heart = S.bFallen ? MakeFallenHeart() : nullptr;
        // own: [mini] 12 [name / hp] 12 [fallen heart]; the opponent's (CX-09): [fallen heart] [mini] 12 [name / hp] with
        // the text on the right edge of the column
        const TArray<UWidget*> Order = bOpp ? TArray<UWidget*>{Heart, Mini, Text} : TArray<UWidget*>{Mini, Text, Heart};
        bool bFirstPart = true;
        for (UWidget* Part : Order) {
          if (!Part) continue;
          if (UHorizontalBoxSlot* RS = Row->AddChildToHorizontalBox(Part)) {
            RS->SetVerticalAlignment(VAlign_Top);
            RS->SetPadding(FMargin(bFirstPart ? 0.0f : 12.0f, 0.0f, 0.0f, 0.0f));
          }
          bFirstPart = false;
        }
        if (UHorizontalBoxSlot* C = SidekickRow->AddChildToHorizontalBox(Row)) {
          C->SetVerticalAlignment(VAlign_Top);
          C->SetPadding(FMargin(I > 0 ? 12.0f : 0.0f, 0.0f, 0.0f, 0.0f));
        }
      }
      ++SidekickItems;
    }
    return;
  }
  // ---- S: the sidekicks in the tooltip of the panel (04 §2.2, ВР-VS2-CX09-06): one hud.panel.sidekick row each ----
  UBorder* Tip = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
  if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), Model.PxPerSu)) Tip->SetBrush(*Skin);
  Tip->SetPadding(FMargin(10.0f));
  UVerticalBox* Rows = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
  Tip->SetContent(Rows);
  const bool bAnyFallen = Model.Sidekicks.ContainsByPredicate([](const FUmSidekickView& S) { return S.bFallen; });
  for (const FUmSidekickView& S : Model.Sidekicks) {
    UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    if (bAnyFallen) {
      // the fallen heart 24 su before a fallen sidekick, the same room before the others (one text column)
      UWidget* Lead = S.bFallen ? MakeFallenHeart() : nullptr;
      if (!Lead) {
        USizeBox* Spacer = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        Spacer->SetWidthOverride(UmHudPanel::HeartSu);
        Spacer->SetHeightOverride(UmHudPanel::HeartSu);
        Lead = Spacer;
      }
      if (UHorizontalBoxSlot* H = Row->AddChildToHorizontalBox(Lead)) {
        H->SetVerticalAlignment(VAlign_Center);
        H->SetPadding(FMargin(0.0f, 0.0f, 6.0f, 0.0f));
      }
    }
    UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    T->SetFont(Theme.Font(TEXT("type.tag")));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    T->SetText(UmHudPanel::SidekickLine(S));
    if (UHorizontalBoxSlot* TS = Row->AddChildToHorizontalBox(T)) TS->SetVerticalAlignment(VAlign_Center);
    if (UVerticalBoxSlot* RS = Rows->AddChildToVerticalBox(Row)) RS->SetPadding(FMargin(0.0f, TooltipRows ? 4.0f : 0.0f, 0.0f, 0.0f));
    ++TooltipRows;
  }
  SidekickTip = Tip;
  SetToolTip(Tip);
}

void UUmHudPlayerPanel::ApplyModel(const FUmPlayerPanelModel& InModel) {
  if (bHasModel && Model == InModel) return;
  const bool bFirst = !bHasModel;
  const FUmPlayerPanelModel Old = Model;
  Model = InModel;
  bHasModel = true;
  ApplyGeometry();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (NameText && (bFirst || Old.HeroName != Model.HeroName)) {
    NameText->SetText(FText::FromString(Model.HeroName));  // hero name: server data
    NameText->SetFont(Theme.Font(UmHudPanel::NameFontToken(Model.HeroName)));
  }
  // the monogram of the fallback circle is the hero's (CP-08); the name's slug picks the avatar until a key is set
  if (Portrait && !Model.HeroName.IsEmpty()) Portrait->SetHeroName(Model.HeroName);
  if (bFirst || Old.State != Model.State) {
    // hud.csv HB-18 timing: the status word of the turn fades out over 120 ms (icon.leave.ms), then the new one stands;
    // the first model, reduced motion and an empty old word switch at once
    const bool bFade = !bFirst && !IsReduced() && StatusText && !UmHudPanel::StatusText(Old.State).IsEmpty();
    StatusFadeStart = bFade ? Now() : -1.0;
    if (!bFade) ApplyStatus(Model.State);
    if (Portrait) {
      // CP-08 / 04 §2.2: the fallen hero's circle loses its colour (the cross on the heart is the portrait's AB-8)
      const bool bFallen = Model.State == EUmPanelState::Fallen;
      if (bFallen || Portrait->GetPortraitState() == EUmPortraitState::Fallen) {
        Portrait->SetPortraitState(bFallen ? EUmPortraitState::Fallen : EUmPortraitState::Avatar, false);
      }
    }
  }
  if (HpText && (bFirst || Old.Hp != Model.Hp || Old.MaxHp != Model.MaxHp || Old.bHasHp != Model.bHasHp)) {
    HpText->SetText(Model.bHasHp ? UmHudPanel::HpText(Model.Hp, Model.MaxHp) : FText::GetEmpty());
  }
  if (bFirst || Old.Sidekicks != Model.Sidekicks || Old.bClassS != Model.bClassS || Old.PxPerSu != Model.PxPerSu) {
    RebuildSidekicks();
  }
}

// ------------------------------------------------------------------------------------------------- motion, input

bool UUmHudPlayerPanel::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

double UUmHudPlayerPanel::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

float UUmHudPlayerPanel::GetDotOpacity() const { return PulseDot ? PulseDot->GetRenderOpacity() : 0.0f; }

void UUmHudPlayerPanel::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  StepMotion();
}

void UUmHudPlayerPanel::ApplyStatus(EUmPanelState State) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (StatusText) {
    const FText Status = UmHudPanel::StatusText(State);
    StatusText->SetText(Status);
    StatusText->SetColorAndOpacity(FSlateColor(Theme.Color(UmHudPanel::StatusColorToken(State))));
    StatusText->SetRenderOpacity(1.0f);
    // their turn: no word, the row keeps its height (the HP row does not jump)
    StatusText->SetVisibility(Status.IsEmpty() ? ESlateVisibility::Hidden : ESlateVisibility::HitTestInvisible);
  }
  if (PulseDot) {
    PulseDot->SetVisibility(State == EUmPanelState::Ai ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    PulseDot->SetRenderOpacity(1.0f);
    PulseStart = Now();
  }
}

void UUmHudPlayerPanel::StepMotion() {
  if (StatusFadeStart >= 0.0) {
    const double LeaveMs = FMath::Max(1.0f, UUmHudTheme::Get().Ms(TEXT("icon.leave.ms")));
    const float A = FMath::Clamp(static_cast<float>((Now() - StatusFadeStart) * 1000.0 / LeaveMs), 0.0f, 1.0f);
    if (A >= 1.0f) {
      StatusFadeStart = -1.0;
      ApplyStatus(Model.State);
    } else {
      if (StatusText) StatusText->SetRenderOpacity(1.0f - A);
      if (PulseDot) PulseDot->SetRenderOpacity(1.0f - A);
      return;
    }
  }
  if (!PulseDot || Model.State != EUmPanelState::Ai) return;
  // 04 §2.3: «ИИ думает» - the dot pulses 1 -> 0.35 -> 1 at 1 Hz; reduced motion - static
  float Dot = 1.0f;
  if (!IsReduced()) {
    const double Phase = FMath::Fmod((Now() - PulseStart) * 1000.0, 1000.0) / 1000.0;
    Dot = 0.35f + 0.65f * static_cast<float>(0.5 + 0.5 * FMath::Cos(2.0 * PI * Phase));
  }
  if (!FMath::IsNearlyEqual(PulseDot->GetRenderOpacity(), Dot, 1.0e-3f)) PulseDot->SetRenderOpacity(Dot);
}

void UUmHudPlayerPanel::SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                                 const FS09OnHudPressOutcome& InOnOutcome) {
  PressId = InId;
  Arbiter = InArbiter;
  OnOutcome = InOnOutcome;
}

FReply UUmHudPlayerPanel::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  // DE-014: the press belongs to the logical id, the release decides
  Arbiter->Press(PressId, Arbiter->Now());
  FReply Reply = FReply::Handled();
  if (const TSharedPtr<SWidget> Cached = GetCachedWidget()) Reply.CaptureMouse(Cached.ToSharedRef());
  return Reply;
}

FReply UUmHudPlayerPanel::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  const bool bOver = InGeometry.IsUnderLocation(InMouseEvent.GetScreenSpacePosition());
  const FS09HudPressOutcome Outcome = Arbiter->Release(bOver ? PressId : NAME_None, Arbiter->Now());
  if (Outcome.Result == ES09HudPressResult::Act || Outcome.Result == ES09HudPressResult::Refused) {
    OnOutcome.ExecuteIfBound(FS09HudPressArbiter::Decide(Outcome, FS09Reason()));
  }
  return FReply::Handled().ReleaseMouseCapture();
}

// ------------------------------------------------------------------------------------------------- SHOT

void UUmHudPlayerPanel::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const {
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && bHasModel;
  const bool bPainted = bVisible && !Rect.IsEmpty();
  const int32 Fallen = Model.Sidekicks.FilterByPredicate([](const FUmSidekickView& S) { return S.bFallen; }).Num();
  const FString Extra = FString::Printf(
      TEXT("hero=%s hp=%d/%d sidekicks=%d fallen=%d tracker=%d/%d ring=%d avatar=%d class=%s smoulder=%.2f"),
      *Model.HeroName.Replace(TEXT(" "), TEXT("_")), Model.Hp, Model.MaxHp, Model.Sidekicks.Num(), Fallen,
      Portrait ? Portrait->GetTrackerShown() : 0, Portrait ? Portrait->GetTrackerSlots() : 0,
      Portrait && Portrait->IsRingShown() ? 1 : 0, Portrait && Portrait->IsAvatarShown() ? 1 : 0,
      Model.bClassS ? TEXT("S") : TEXT("L"), Portrait ? Portrait->GetRingSmoulder() : 0.0f);
  Out.Add(S08ArtHud::FormatWidgetLineEx(UmHudPanel::ShotId(Side), TEXT("umg"), UmHudPanel::StateName(Model.State),
                                        FString(), Rect, bPainted, bVisible, SourceName(), Extra));
}

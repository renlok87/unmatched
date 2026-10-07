// VS-3 CP-15...CP-20: the card widget - see UmCardWidget.h.
#include "UmCardWidget.h"

#include "../../S09/S09CombatStage.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08ArtLook.h"
#include "../S08IconMotion.h"
#include "UmCardMedia.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/AssetManager.h"
#include "Engine/StreamableManager.h"
#include "Engine/Texture2D.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Internationalization.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmCard, Log, All);

const TCHAR* const UUmCardWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmCard");

// ------------------------------------------------------------------------------------------------ helpers

namespace UmCardWidget {
const TCHAR* ShowName(EUmCardShow Show) {
  switch (Show) {
    case EUmCardShow::Hand: return TEXT("hand");
    case EUmCardShow::Hover: return TEXT("hover");
    case EUmCardShow::Combat: return TEXT("combat");
    case EUmCardShow::Slot: return TEXT("slot");
    case EUmCardShow::Inspector: return TEXT("inspector");
    case EUmCardShow::DeckGrid: return TEXT("deckgrid");
    case EUmCardShow::ClassSHand: return TEXT("classS-hand");
    case EUmCardShow::ClassSCombat: return TEXT("classS-combat");
    case EUmCardShow::MiniOpp: return TEXT("mini-48x67");
    case EUmCardShow::MiniChip: return TEXT("mini-32x45");
    case EUmCardShow::ClassSInspector: return TEXT("classS-inspector");
  }
  return TEXT("hand");
}

const TCHAR* FaceName(EUmCardFace Face) {
  switch (Face) {
    case EUmCardFace::Ru: return TEXT("ru");
    case EUmCardFace::En: return TEXT("en");
    case EUmCardFace::Back: return TEXT("back");
    default: return TEXT("fallback");
  }
}

bool IsMini(EUmCardShow Show) { return Show == EUmCardShow::MiniOpp || Show == EUmCardShow::MiniChip; }

float BandOf(EUmCardShow Show) { return IsMini(Show) ? MiniBandSu : BandSu; }

FVector2D ShowSize(EUmCardShow Show, bool bEnglishScan) {
  switch (Show) {
    case EUmCardShow::Hover: return FVector2D(225.0, 312.0);
    case EUmCardShow::Combat: return FVector2D(230.0, 319.0);
    case EUmCardShow::Slot: return FVector2D(190.0, 264.0);
    case EUmCardShow::Inspector: return bEnglishScan ? FVector2D(408.0, 566.0) : FVector2D(460.0, 640.0);
    case EUmCardShow::ClassSInspector: return FVector2D(400.0, 555.0);
    case EUmCardShow::ClassSHand: return FVector2D(120.0, 166.0);
    case EUmCardShow::MiniOpp: return FVector2D(48.0, 67.0);
    case EUmCardShow::MiniChip: return FVector2D(32.0, 45.0);
    case EUmCardShow::Hand:
    case EUmCardShow::DeckGrid:
    case EUmCardShow::ClassSCombat:
    default: return FVector2D(150.0, 208.0);
  }
}

FString Slug(const FString& Name) {
  // INT-014 / CP-15 p. 2: lower case, ' ' -> '-', anything but a-z 0-9 '-' dropped (runs of '-' collapse, ends trimmed:
  // the registry keys of ue_import_card_media.py)
  FString Out;
  for (const TCHAR C : Name.ToLower()) {
    if ((C >= TEXT('a') && C <= TEXT('z')) || (C >= TEXT('0') && C <= TEXT('9'))) {
      Out.AppendChar(C);
    } else if ((C == TEXT(' ') || C == TEXT('-')) && !Out.IsEmpty() && !Out.EndsWith(TEXT("-"))) {
      Out.AppendChar(TEXT('-'));
    }
  }
  while (Out.EndsWith(TEXT("-"))) Out.LeftChopInline(1);
  return Out;
}

FString CardKey(const FString& HeroSlug, const FString& CardName) {
  const FString CardSlug = Slug(CardName);
  return HeroSlug.IsEmpty() || CardSlug.IsEmpty() ? FString() : HeroSlug + TEXT(":") + CardSlug;
}

FIntPoint DrawnSrcPx(const FUmCardMediaEntry& Entry) {
  if (Entry.Kind == TEXT("back")) return FIntPoint(FMath::Max(1, Entry.Src.X - 2 * BackCropPx), Entry.Src.Y);
  return Entry.Src;
}

FVector4 UvRect(const FUmCardMediaEntry& Entry) {
  if (Entry.Kind == TEXT("back") && Entry.Pad.X > 0) {
    // ВР-VS2-CP-03: the sides of the back cropped 5 px each (10 / 768 = 1.30 %), the logo stays; then contain
    const double Crop = static_cast<double>(BackCropPx) / Entry.Pad.X;
    return FVector4(Crop, 0.0, Entry.Uv.X - Crop, Entry.Uv.Y);
  }
  return FVector4(0.0, 0.0, Entry.Uv.X, Entry.Uv.Y);
}

FUmCardFit Fit(const FVector2D& ShowSu, float Band, const FIntPoint& Src, float PxPerSu, float Cap) {
  FUmCardFit F;
  F.ShowSu = ShowSu;
  F.CardSu = ShowSu;
  F.WindowSu = ShowSu - FVector2D(2.0 * Band, 2.0 * Band);
  if (Src.X <= 0 || Src.Y <= 0 || F.WindowSu.X <= 0.0 || F.WindowSu.Y <= 0.0) return F;
  const float Px = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  // contain (ВР-CP05): su per source pixel - the smaller ratio, never a crop
  double K = FMath::Min(F.WindowSu.X / Src.X, F.WindowSu.Y / Src.Y);
  if (K * Px > Cap + 1.0e-4) {
    // ВР-CP04: the card shrinks (the band stays 4 su) until the scan is Cap x its source pixels; the rest is padding
    const double KCap = Cap / Px;
    const double Fw = (KCap * Src.X + 2.0 * Band) / ShowSu.X;
    const double Fh = (KCap * Src.Y + 2.0 * Band) / ShowSu.Y;
    const double Fs = FMath::Min(1.0, FMath::Max(Fw, Fh));
    F.CardSu = ShowSu * Fs;
    F.WindowSu = F.CardSu - FVector2D(2.0 * Band, 2.0 * Band);
    K = FMath::Min(F.WindowSu.X / Src.X, F.WindowSu.Y / Src.Y);
    F.bCapped = Fs < 1.0 - 1.0e-4;
  }
  F.ScanSu = FVector2D(Src.X * K, Src.Y * K);
  F.Scale = static_cast<float>(K * Px);
  return F;
}

float HoverScaleFor(const FUmCardFit& Base, float Cap, float MaxScale) {
  if (Base.Scale <= 0.0f) return MaxScale;
  return FMath::Clamp(Cap / Base.Scale, 1.0f, MaxScale);
}

float HoverScaleOf(EUmCardShow Show) { return Show == EUmCardShow::ClassSHand ? HoverScaleClassS : HoverScale; }

float ChipSuFor(float PxPerSu) { return PxPerSu > 0.0f && PxPerSu < 1.0f - 1.0e-4f ? ChipSmallDpiSu : ChipSu; }

FName FrameKey(bool bMini, bool bWarning, bool bSelected, bool bHover) {
  if (bMini) return FName(TEXT("card.frame.mini"));  // ВР-VS2-CP-06: the mini displays are mini-idle only
  if (bWarning) return FName(TEXT("card.frame.warning"));
  if (bSelected) return FName(TEXT("card.frame.selected"));
  if (bHover) return FName(TEXT("card.frame.hover"));
  return FName(TEXT("card.frame.idle"));
}

float AppearScale(float TMs) {
  if (TMs <= 0.0f) return 0.8f;
  if (TMs < 72.0f) return FMath::Lerp(0.8f, 1.04f, S08IconMotion::Ease(ES08IconEase::EaseOutCubic, TMs / 72.0f));
  if (TMs < 180.0f) {
    return FMath::Lerp(1.04f, 1.0f, S08IconMotion::Ease(ES08IconEase::EaseInOutCubic, (TMs - 72.0f) / 108.0f));
  }
  return 1.0f;
}

float AppearOpacity(float TMs) {
  if (TMs <= 0.0f) return 0.15f;
  if (TMs < 120.0f) return FMath::Lerp(0.15f, 1.0f, S08IconMotion::Ease(ES08IconEase::EaseOutQuad, TMs / 120.0f));
  return 1.0f;
}

float LeaveScale(float TMs) {
  return FMath::Lerp(1.0f, 0.92f, S08IconMotion::Ease(ES08IconEase::EaseInQuad, FMath::Clamp(TMs / 120.0f, 0.0f, 1.0f)));
}

float LeaveOpacity(float TMs) {
  return FMath::Lerp(1.0f, 0.0f, S08IconMotion::Ease(ES08IconEase::EaseInQuad, FMath::Clamp(TMs / 120.0f, 0.0f, 1.0f)));
}

float FlipScaleX(float TMs, float TotalMs) {
  if (TotalMs <= 0.0f || TMs >= TotalMs || TMs <= 0.0f) return 1.0f;
  const float Half = 0.5f * TotalMs;
  if (TMs < Half) return 1.0f - S08IconMotion::Ease(ES08IconEase::EaseInQuad, TMs / Half);
  return S08IconMotion::Ease(ES08IconEase::EaseOutQuad, (TMs - Half) / Half);
}

float DefenseFlipDelayMs(float SpeedMul) {
  return static_cast<float>(FS09CombatTiming::DefenseFlipDelayMs) * FMath::Max(0.0f, SpeedMul);
}

float PlayedFlashMs(float SpeedScale, bool bReduced) {
  if (SpeedScale <= 0.0f) return 0.0f;  // UI-ACC-013 «Нет»: the animations are instant - no flash
  return bReduced ? FlashReducedMs : FlashMs * SpeedScale;
}

float FlashOpacity(float TMs, float DurMs) {
  if (DurMs <= 0.0f || TMs < 0.0f || TMs >= DurMs) return 0.0f;
  return 1.0f - TMs / DurMs;
}

FString FlashCueLine(int32 Seq, int64 TMs, bool bReduced) {
  return FString::Printf(TEXT("CUE fx id=CUE-006 subject=card seq=%d t=%lld vfx=none sfx=none clip=none mat=none socket=- "
                              "reduced=%d result=spawned"),
                         Seq, TMs, bReduced ? 1 : 0);
}

FString FlashDoneLine(int32 Seq, int64 TMs, int64 Ms, const TCHAR* Cut) {
  return FString::Printf(TEXT("CUE fx done id=CUE-006 subject=card seq=%d t=%lld ms=%lld cut=%s"), Seq, TMs, Ms, Cut);
}

FString TraceLine(const FString& Key, EUmCardFace Face, const FString& Tex, EUmCardShow Show, const FUmCardFit& F,
                  float PxPerSu, const FString& State, bool bChip) {
  const float Px = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  return FString::Printf(TEXT("CARD-ART key=%s lang=%s tex=%s show=%s su=%.0fx%.0f px=%.0fx%.0f scale=%.3f capped=%d "
                              "state=%s chip=%d"),
                         Key.IsEmpty() ? TEXT("none") : *Key, FaceName(Face), Tex.IsEmpty() ? TEXT("fallback") : *Tex,
                         ShowName(Show), F.CardSu.X, F.CardSu.Y, F.ScanSu.X * Px, F.ScanSu.Y * Px, F.Scale,
                         F.bCapped ? 1 : 0, State.IsEmpty() ? TEXT("idle") : *State, bChip ? 1 : 0);
}
}  // namespace UmCardWidget

namespace {
template <typename T>
T* UmCardFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

/** The fallback frame of a state before the CP-14 import (the rounded outline of the token, no texture). */
FSlateBrush UmCardOutline(FName Key, float RadiusSu) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  FName Token(TEXT("panel.edge"));
  float Width = 1.0f;
  if (Key == FName(TEXT("card.frame.hover"))) {
    Token = TEXT("card.cream");
  } else if (Key == FName(TEXT("card.frame.selected"))) {
    Token = TEXT("state.pending");
    Width = 3.0f;
  } else if (Key == FName(TEXT("card.frame.warning"))) {
    Token = TEXT("state.warning");
    Width = 2.0f;
  } else if (Key == FName(TEXT("card.frame.flash"))) {
    Token = TEXT("fx.flash");
    Width = 2.0f;
  } else if (Key == FName(TEXT("card.frame.focus"))) {
    Token = TEXT("card.glyph");
    Width = 2.0f;
  }
  return FSlateRoundedBoxBrush(FLinearColor::Transparent, RadiusSu, Theme.Color(Token), Width);
}
}  // namespace

// ------------------------------------------------------------------------------------------------ tree

UClass* UUmCardWidget::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmCardWidget::StaticClass(), WidgetBlueprintPath); }

bool UUmCardWidget::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  using namespace UmCardWidget;
  const FVector2D Hand = ShowSize(EUmCardShow::Hand);
  USizeBox* BoxW = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("Box")));
  BoxW->SetWidthOverride(Hand.X);
  BoxW->SetHeightOverride(Hand.Y);
  if (!Attach(BoxW, nullptr)) return Fail(TEXT("Box"));
  UOverlay* Stack = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("Stack")));
  if (!Attach(Stack, BoxW)) return Fail(TEXT("Stack"));
  USizeBox* CardW = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("Card")));
  CardW->SetWidthOverride(Hand.X);
  CardW->SetHeightOverride(Hand.Y);
  if (!Attach(CardW, Stack)) return Fail(TEXT("Card"));
  if (UOverlaySlot* S = Cast<UOverlaySlot>(CardW->Slot)) {
    S->SetHorizontalAlignment(HAlign_Center);
    S->SetVerticalAlignment(VAlign_Center);
  }
  UOverlay* L = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("Layers")));
  if (!Attach(L, CardW)) return Fail(TEXT("Layers"));
  auto Layer = [&](UWidget* W, EHorizontalAlignment H, EVerticalAlignment V, const FMargin& Pad, bool bShown) {
    if (!Attach(W, L)) return false;
    if (UOverlaySlot* S = Cast<UOverlaySlot>(W->Slot)) {
      S->SetHorizontalAlignment(H);
      S->SetVerticalAlignment(V);
      S->SetPadding(Pad);
    }
    W->SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    return true;
  };
  // the focus ring sits outside the keyline: gap 2 su + ring 2 su (02 §4.3, ВР-CP06)
  UImage* Focus = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("FocusRing")));
  if (!Layer(Focus, HAlign_Fill, VAlign_Fill, FMargin(-FocusOutsetSu), false)) return Fail(TEXT("FocusRing"));
  UImage* Under = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Underlay")));
  if (!Layer(Under, HAlign_Fill, VAlign_Fill, FMargin(UnderlayInsetSu), true)) return Fail(TEXT("Underlay"));
  UImage* FaceW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Face")));
  if (!Layer(FaceW, HAlign_Center, VAlign_Center, FMargin(0.0f), false)) return Fail(TEXT("Face"));
  // 02 §6.1 fallback: type discs, the name of the data, the "EN" tag (INT-018 p. 3), value and BOOST, the banner
  UVerticalBox* Fb = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Fallback")));
  if (!Layer(Fb, HAlign_Fill, VAlign_Fill, FMargin(BandSu + 6.0f), false)) return Fail(TEXT("Fallback"));
  UHorizontalBox* Types = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("FallbackTypes")));
  if (!Attach(Types, Fb)) return Fail(TEXT("FallbackTypes"));
  if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Types->Slot)) S->SetHorizontalAlignment(HAlign_Center);
  for (const TCHAR* Name : {TEXT("TypeIcon0"), TEXT("TypeIcon1")}) {
    US08AnimatedIconWidget* Icon = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(Name));
    if (!Attach(Icon, Types)) return Fail(Name);
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(Icon->Slot)) S->SetPadding(FMargin(2.0f, 0.0f));
  }
  for (const TCHAR* Name : {TEXT("FallbackName"), TEXT("FallbackLang"), TEXT("FallbackValues"), TEXT("FallbackBanner")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetJustification(ETextJustify::Center);
    T->SetAutoWrapText(true);
    if (!Attach(T, Fb)) return Fail(Name);
    if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(T->Slot)) {
      S->SetHorizontalAlignment(HAlign_Fill);
      S->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 0.0f));
    }
  }
  US08AnimatedIconWidget* Plate = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("PlateIcon")));
  if (!Layer(Plate, HAlign_Center, VAlign_Center, FMargin(0.0f), false)) return Fail(TEXT("PlateIcon"));
  US08AnimatedIconWidget* Spin = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("Spinner")));
  if (!Layer(Spin, HAlign_Center, VAlign_Center, FMargin(0.0f), false)) return Fail(TEXT("Spinner"));
  UImage* FrameW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Frame")));
  if (!Layer(FrameW, HAlign_Fill, VAlign_Fill, FMargin(0.0f), true)) return Fail(TEXT("Frame"));
  UImage* Flash = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("FlashLayer")));
  if (!Layer(Flash, HAlign_Fill, VAlign_Fill, FMargin(0.0f), false)) return Fail(TEXT("FlashLayer"));
  // CP-16: the dot's centre 10 su from the right and the top edge of the frame (10 su image: 8 su + keyline)
  const float DotPad = NewDotCentreInsetSu - 0.5f * NewDotSu;
  UImage* Dot = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("NewDot")));
  if (!Layer(Dot, HAlign_Right, VAlign_Top, FMargin(0.0f, DotPad, DotPad, 0.0f), false)) return Fail(TEXT("NewDot"));
  US08AnimatedIconWidget* Drop = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("DropIcon")));
  if (!Layer(Drop, HAlign_Center, VAlign_Top, FMargin(0.0f, ChipTopSu, 0.0f, 0.0f), false)) return Fail(TEXT("DropIcon"));
  UOverlay* Chip = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("BoostChip")));
  if (!Layer(Chip, HAlign_Center, VAlign_Top, FMargin(0.0f, ChipTopSu, 0.0f, 0.0f), false)) return Fail(TEXT("BoostChip"));
  US08AnimatedIconWidget* ChipIcon = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("BoostIcon")));
  if (!Attach(ChipIcon, Chip)) return Fail(TEXT("BoostIcon"));
  UTextBlock* ChipText = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("BoostText")));
  ChipText->SetJustification(ETextJustify::Center);
  if (!Attach(ChipText, Chip)) return Fail(TEXT("BoostText"));
  if (UOverlaySlot* S = Cast<UOverlaySlot>(ChipText->Slot)) {
    S->SetHorizontalAlignment(HAlign_Center);
    S->SetVerticalAlignment(VAlign_Center);
  }
  return true;
}

bool UUmCardWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogUmCard, Error, TEXT("UMCARD default tree: %s"), *Error);
  }
  Box = UmCardFind<USizeBox>(WidgetTree, TEXT("Box"));
  Card = UmCardFind<USizeBox>(WidgetTree, TEXT("Card"));
  Layers = UmCardFind<UOverlay>(WidgetTree, TEXT("Layers"));
  Underlay = UmCardFind<UImage>(WidgetTree, TEXT("Underlay"));
  Face = UmCardFind<UImage>(WidgetTree, TEXT("Face"));
  Frame = UmCardFind<UImage>(WidgetTree, TEXT("Frame"));
  FlashLayer = UmCardFind<UImage>(WidgetTree, TEXT("FlashLayer"));
  FocusRing = UmCardFind<UImage>(WidgetTree, TEXT("FocusRing"));
  NewDot = UmCardFind<UImage>(WidgetTree, TEXT("NewDot"));
  BoostChip = UmCardFind<UOverlay>(WidgetTree, TEXT("BoostChip"));
  BoostIcon = UmCardFind<US08AnimatedIconWidget>(WidgetTree, TEXT("BoostIcon"));
  BoostText = UmCardFind<UTextBlock>(WidgetTree, TEXT("BoostText"));
  DropIcon = UmCardFind<US08AnimatedIconWidget>(WidgetTree, TEXT("DropIcon"));
  PlateIcon = UmCardFind<US08AnimatedIconWidget>(WidgetTree, TEXT("PlateIcon"));
  Spinner = UmCardFind<US08AnimatedIconWidget>(WidgetTree, TEXT("Spinner"));
  Fallback = UmCardFind<UVerticalBox>(WidgetTree, TEXT("Fallback"));
  FallbackTypes = UmCardFind<UHorizontalBox>(WidgetTree, TEXT("FallbackTypes"));
  TypeIcon0 = UmCardFind<US08AnimatedIconWidget>(WidgetTree, TEXT("TypeIcon0"));
  TypeIcon1 = UmCardFind<US08AnimatedIconWidget>(WidgetTree, TEXT("TypeIcon1"));
  FallbackName = UmCardFind<UTextBlock>(WidgetTree, TEXT("FallbackName"));
  FallbackLang = UmCardFind<UTextBlock>(WidgetTree, TEXT("FallbackLang"));
  FallbackValues = UmCardFind<UTextBlock>(WidgetTree, TEXT("FallbackValues"));
  FallbackBanner = UmCardFind<UTextBlock>(WidgetTree, TEXT("FallbackBanner"));
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  // the icons and fonts are set at run time (a WBP keeps neither the icon state nor the default composite font)
  auto Icon = [](US08AnimatedIconWidget* W, const TCHAR* Id, float Su) {
    if (W && W->SetIcon(FName(Id), Su, 24)) {
      W->SetDisplaySizeSu(Su);
      W->ShowAtRest();
    }
  };
  Icon(BoostIcon, TEXT("state-boost"), UmCardWidget::ChipSu);
  Icon(DropIcon, TEXT("card-drop"), UmCardWidget::ChipSu);
  Icon(PlateIcon, TEXT("resource-card"), 24.0f);
  Icon(Spinner, TEXT("loader-spinner"), UmCardWidget::SpinnerSu);
  if (BoostText) {
    // shape.boost_disc: the digit's cap ~ 0.37 of the 24 su disc - the font.card face (Roboto Bold Condensed)
    FSlateFontInfo Font = Theme.Font(TEXT("type.tag"));
    Font.Size = UmHudTheme::PointsFromSu(12.0f);
    BoostText->SetFont(Font);
    BoostText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.glyph"))));
  }
  if (FallbackName) FallbackName->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  if (FallbackLang) {
    FallbackLang->SetFont(Theme.Font(TEXT("type.caption")));
    FallbackLang->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  }
  if (FallbackValues) {
    FallbackValues->SetFont(Theme.Font(TEXT("type.tag")));
    FallbackValues->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.cream"))));
  }
  if (FallbackBanner) {
    FallbackBanner->SetFont(Theme.Font(TEXT("type.caption")));
    FallbackBanner->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  }
  // M_UmCardFace (CP-14): one MID per widget, reused for every face of the pool
  if (UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr, UmCardWidget::MaterialPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) {
    FaceMid = UMaterialInstanceDynamic::Create(Mat, this);
  }
  for (UWidget* W : {static_cast<UWidget*>(Box), static_cast<UWidget*>(Card), static_cast<UWidget*>(Layers)}) {
    if (W) W->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  if (Card) Card->SetRenderTransformPivot(FVector2D(0.5, 1.0));  // hover from the bottom centre; the flip about x 0.5
  SetVisibility(ESlateVisibility::Visible);  // the card takes the pointer (hover, press, inspector)
  ApplyCursor();
  ApplyLayout();
  ApplyFrame();
  return bFirst;
}

bool UUmCardWidget::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Box) Missing.Add(TEXT("Box"));
  if (!Card) Missing.Add(TEXT("Card"));
  if (!Layers) Missing.Add(TEXT("Layers"));
  if (!Underlay) Missing.Add(TEXT("Underlay"));
  if (!Face) Missing.Add(TEXT("Face"));
  if (!Frame) Missing.Add(TEXT("Frame"));
  if (!FlashLayer) Missing.Add(TEXT("FlashLayer"));
  if (!FocusRing) Missing.Add(TEXT("FocusRing"));
  if (!NewDot) Missing.Add(TEXT("NewDot"));
  if (!BoostChip) Missing.Add(TEXT("BoostChip"));
  if (!BoostText) Missing.Add(TEXT("BoostText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmCardWidget::NativeConstruct() {
  Super::NativeConstruct();
  if (!CultureHandle.IsValid()) {
    // CP-15: the language follows the culture in the frame it changes (no animation)
    CultureHandle = FInternationalization::Get().OnCultureChanged().AddWeakLambda(this, [this]() {
      if (bHasModel && StateModel.Lang.IsEmpty()) {
        ResolveFace();
        ApplyLayout();
      }
    });
  }
}

void UUmCardWidget::NativeDestruct() {
  if (CultureHandle.IsValid()) {
    FInternationalization::Get().OnCultureChanged().Remove(CultureHandle);
    CultureHandle.Reset();
  }
  if (LoadHandle.IsValid()) LoadHandle->CancelHandle();
  LoadHandle.Reset();
  PreloadHandle.Reset();
  Super::NativeDestruct();
}

// ------------------------------------------------------------------------------------------------ model and face

bool UUmCardWidget::IsLegacy() const {
  return LegacyOverride >= 0 ? LegacyOverride == 1 : !S08ArtLook::CardArt();
}

bool UUmCardWidget::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

double UUmCardWidget::NowMs() const {
  return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0;
}

float UUmCardWidget::GetPxPerSu() const {
  if (StateModel.PxPerSu > 0.0f) return StateModel.PxPerSu;
  const FUmHudScaleState& S = UmHudScale::Current();
  return S.Window.X > 0 && S.PxPerSu() > 0.0f ? S.PxPerSu() : 1.0f;
}

void UUmCardWidget::ApplyModel(const FS09CardView& InCard, const FUmCardState& InState) {
  auto SameFace = [](const FS09CardView& A, const FS09CardView& B) {
    return A.InstanceId == B.InstanceId && A.CardId == B.CardId && A.Name == B.Name && A.NameRu == B.NameRu &&
           A.CardType == B.CardType && A.AttackValue == B.AttackValue && A.DefenseValue == B.DefenseValue &&
           A.BoostValue == B.BoostValue && A.bHasBoostValue == B.bHasBoostValue && A.BannerName == B.BannerName &&
           A.bHidden == B.bHidden;
  };
  // QA-005: a card face down keeps no face in the widget - only its instance id
  FS09CardView Kept;
  if (InState.bFaceDown) {
    Kept.InstanceId = InCard.InstanceId;
    Kept.bHidden = true;
  } else {
    Kept = InCard;
  }
  if (bHasModel && InState == StateModel && SameFace(Kept, CardModel)) return;
  const bool bLayoutOnly = bHasModel && SameFace(Kept, CardModel) && InState.HeroSlug == StateModel.HeroSlug &&
                           InState.bFaceDown == StateModel.bFaceDown && InState.Lang == StateModel.Lang;
  CardModel = Kept;
  StateModel = InState;
  bHasModel = true;
  if (!bLayoutOnly) {
    // a model change ends a flip in flight (a reconnect, a new snapshot): the model wins
    FlipStartMs = -1.0;
    PendingFace.Reset();
    bFaceDownNow = InState.bFaceDown;
    bRevealed = false;
    ResolveFace();
  }
  ApplyLayout();
  ApplyFrame();
  Step();
}

void UUmCardWidget::FallBack(const TCHAR* Why) {
  FaceTexture = nullptr;
  bLoading = false;
  SrcPx = FIntPoint::ZeroValue;
  if (FaceKind != EUmCardFace::Back) FaceKind = EUmCardFace::Fallback;
  const bool bLegacy = IsLegacy();
  TexPath = bLegacy ? TEXT("legacy") : TEXT("fallback");
  if (!bLegacy && !bWarnedFallback) {
    // INT-018 p. 4: the missing art is logged with its key, the match goes on
    bWarnedFallback = true;
    UE_LOG(LogUmCard, Warning, TEXT("CARD-ART fallback key=%s reason=%s"), FaceKey.IsEmpty() ? TEXT("none") : *FaceKey, Why);
  }
  ApplyFallbackContent();
}

void UUmCardWidget::ResolveFace() {
  LoadingPath.Reset();
  if (LoadHandle.IsValid()) LoadHandle->CancelHandle();
  LoadHandle.Reset();
  bLoading = false;
  const FString Hero = StateModel.HeroSlug;
  if (bFaceDownNow) {
    FaceKind = EUmCardFace::Back;
    FaceKey = Hero.IsEmpty() ? FString() : TEXT("back:") + Hero;
    if (IsLegacy()) return FallBack(TEXT("legacy"));
    const FUmCardMediaEntry* Entry = Hero.IsEmpty() ? nullptr : UmCardMedia::FindBack(Hero);
    if (!Entry) return FallBack(Hero.IsEmpty() ? TEXT("no-hero") : TEXT("no-registry-entry"));
    LoadFace(*Entry);
    return;
  }
  const FString Lang = StateModel.Lang.IsEmpty() ? UmCardMedia::PreferredLang() : StateModel.Lang.ToLower();
  FaceKind = Lang == TEXT("en") ? EUmCardFace::En : EUmCardFace::Ru;
  FaceKey = UmCardWidget::CardKey(Hero, CardModel.Name);
  if (IsLegacy()) {
    FaceKind = EUmCardFace::Fallback;
    return FallBack(TEXT("legacy"));
  }
  const FUmCardMediaEntry* Entry =
      FaceKey.IsEmpty() ? nullptr : UmCardMedia::FindCard(Hero, UmCardWidget::Slug(CardModel.Name), Lang);
  if (!Entry) {
    FaceKind = EUmCardFace::Fallback;
    return FallBack(FaceKey.IsEmpty() ? TEXT("no-key") : TEXT("no-registry-entry"));
  }
  LoadFace(*Entry);
}

void UUmCardWidget::LoadFace(const FUmCardMediaEntry& Entry) {
  TexPath = Entry.ObjectPath;
  SrcPx = UmCardWidget::DrawnSrcPx(Entry);
  FaceUv = UmCardWidget::UvRect(Entry);
  const FSoftObjectPath Path(Entry.ObjectPath);
  if (bHoldLoading) {
    // the review sheet's «loading» (SC-21): the request is never made, the frame and the delayed spinner stay
    FaceTexture = nullptr;
    bLoading = true;
    SpinnerDelay.End();
    SpinnerDelay.Begin(NowMs());
    LoadingPath = Path;
    return;
  }
  UTexture2D* Tex = Cast<UTexture2D>(Path.ResolveObject());
  if (!Tex && bSyncLoad) Tex = Cast<UTexture2D>(Path.TryLoad());
  if (Tex) {
    SetFaceTexture(Tex);
    return;
  }
  // CP-15: the texture streams in; the frame and loader-spinner 32 su until it is there (HB-47: the spinner only after
  // 300 ms of waiting, 04 §3.3 - a scan that arrives sooner never shows it)
  FaceTexture = nullptr;
  bLoading = true;
  SpinnerDelay.End();
  SpinnerDelay.Begin(NowMs());
  LoadingPath = Path;
  TWeakObjectPtr<UUmCardWidget> WeakThis(this);
  LoadHandle = UAssetManager::GetStreamableManager().RequestAsyncLoad(Path, FStreamableDelegate::CreateLambda([WeakThis]() {
    if (UUmCardWidget* Self = WeakThis.Get()) Self->OnFaceLoaded();
  }));
  if (!LoadHandle.IsValid()) {
    bLoading = false;
    FallBack(TEXT("load-request-failed"));
  }
}

void UUmCardWidget::OnFaceLoaded() {
  if (!bLoading || LoadingPath.IsNull()) return;
  UTexture2D* Tex = Cast<UTexture2D>(LoadingPath.ResolveObject());
  bLoading = false;
  LoadingPath.Reset();
  if (!Tex) {
    FallBack(TEXT("texture-missing"));
  } else {
    SetFaceTexture(Tex);
  }
  ApplyLayout();
  Step();
}

void UUmCardWidget::SetFaceTexture(UTexture2D* Tex) {
  FaceTexture = Tex;
  bLoading = false;
  if (!Face) return;
  FSlateBrush Brush;
  if (FaceMid) {
    FaceMid->SetTextureParameterValue(UmCardWidget::ParamFace, Tex);
    FaceMid->SetVectorParameterValue(UmCardWidget::ParamUvRect, FLinearColor(FaceUv.X, FaceUv.Y, FaceUv.Z, FaceUv.W));
    Brush.SetResourceObject(FaceMid);
  } else {
    // no M_UmCardFace yet (fresh worktree before the CP-14 import): the padded texture through its UV region
    Brush.SetResourceObject(Tex);
    Brush.SetUVRegion(FBox2f(FVector2f(FaceUv.X, FaceUv.Y), FVector2f(FaceUv.Z, FaceUv.W)));
  }
  Brush.ImageSize = FitNow.ScanSu;
  Face->SetBrush(Brush);
}

namespace UmCardWidget {
int32 WrapLines(const FString& Text, float WidthSu, TFunctionRef<float(const FString&)> Measure) {
  TArray<FString> Words;
  Text.ParseIntoArrayWS(Words);
  if (Words.Num() == 0) return 0;
  int32 Lines = 1;
  FString Line;
  for (const FString& W : Words) {
    if (Measure(W) > WidthSu) return MAX_int32;  // one word does not fit at all
    const FString Next = Line.IsEmpty() ? W : Line + TEXT(" ") + W;
    if (Measure(Next) <= WidthSu) {
      Line = Next;
    } else {
      ++Lines;
      Line = W;
    }
  }
  return Lines;
}

FName FitTitleToken(const FString& Name, float WidthSu, int32 MaxLines, const TArray<FName>& Tokens,
                    TFunctionRef<float(const FString&, FName)> Measure) {
  if (Tokens.Num() == 0) return NAME_None;
  for (const FName& T : Tokens) {
    if (WrapLines(Name, WidthSu, [&Measure, &T](const FString& S) { return Measure(S, T); }) <= MaxLines) return T;
  }
  return Tokens.Last();
}
}  // namespace UmCardWidget

void UUmCardWidget::ApplyFallbackContent() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bRuBuild = (StateModel.Lang.IsEmpty() ? UmCardMedia::PreferredLang() : StateModel.Lang.ToLower()) != TEXT("en");
  // INT-018 p. 3: RU missing (or an EN copy in nameRu - the reference DB has that for all 27 MVP cards) -> the EN name
  // with the "EN" tag; the name always comes from the data (02 §3.4), never from a scan
  const bool bRuMissing = bRuBuild && (CardModel.NameRu.IsEmpty() || CardModel.NameRu == CardModel.Name);
  const FString Name = bRuBuild && !bRuMissing ? CardModel.NameRu : CardModel.Name;
  const FVector2D ShowSu = UmCardWidget::ShowSize(StateModel.Show, !bRuBuild);
  if (FallbackName) {
    // VS-5 E4 (VS-4 «Открыто» п. 7, T. Rex «When Dinosaurs Ruled the Earth» in the slot): the title steps down a type
    // until it wraps into 3 lines inside the card (the band + 6 su a side); it never draws past the frame
    TArray<FName> Tokens;
    if (ShowSu.X >= 200.0) Tokens.Add(FName(TEXT("type.heading")));
    Tokens.Append({FName(TEXT("type.button")), FName(TEXT("type.body")), FName(TEXT("type.tag"))});
    const float WidthSu = static_cast<float>(ShowSu.X) - 2.0f * (UmCardWidget::BandSu + 6.0f);
    FName Token = Tokens[0];
    if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer()) {
      const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
      Token = UmCardWidget::FitTitleToken(Name, WidthSu, 3, Tokens, [&Measure, &Theme](const FString& S, FName T) {
        return static_cast<float>(Measure->Measure(S, Theme.Font(T), 1.0f).X);
      });
    }
    FallbackName->SetFont(Theme.Font(Token));
    FallbackName->SetAutoWrapText(true);  // a WBP may not keep the flag of the code tree
    FallbackName->SetClipping(EWidgetClipping::ClipToBounds);
    FallbackName->SetText(FText::FromString(Name));
  }
  if (FallbackLang) {
    FallbackLang->SetText(FText::FromString(TEXT("EN")));
    FallbackLang->SetVisibility(bRuMissing && !Name.IsEmpty() ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  const FString Type = CardModel.CardType.ToUpper();
  const bool bVersatile = Type == TEXT("VERSATILE") || Type == TEXT("UNIVERSAL");
  const TCHAR* First = Type == TEXT("DEFENSE") ? TEXT("action-defense") : Type == TEXT("SCHEME") ? TEXT("action-scheme")
                                                                                                 : TEXT("action-attack");
  if (TypeIcon0 && TypeIcon0->SetIcon(FName(First), 32.0f, 32)) {
    TypeIcon0->SetDisplaySizeSu(32.0f);
    TypeIcon0->ShowAtRest();
  }
  if (TypeIcon1) {
    // a versatile card is attack and defense: both discs (the printed card carries both, not only a colour)
    if (bVersatile && TypeIcon1->SetIcon(FName(TEXT("action-defense")), 32.0f, 32)) {
      TypeIcon1->SetDisplaySizeSu(32.0f);
      TypeIcon1->ShowAtRest();
    }
    TypeIcon1->SetVisibility(bVersatile ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (FallbackValues) {
    TArray<FText> Parts;
    const bool bScheme = Type == TEXT("SCHEME");
    if (!bScheme && !CardModel.Name.IsEmpty()) {
      const int32 Value = Type == TEXT("DEFENSE") ? CardModel.DefenseValue : CardModel.AttackValue;
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(Value));
      Parts.Add(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.value"), A));
    }
    if (CardModel.bHasBoostValue) {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(CardModel.BoostValue));
      Parts.Add(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.boost"), A));
    }
    FallbackValues->SetText(FText::Join(INVTEXT(" · "), Parts));
  }
  if (FallbackBanner) FallbackBanner->SetText(FText::FromString(CardModel.BannerName));
}

// ------------------------------------------------------------------------------------------------ layout and frame

void UUmCardWidget::ApplyLayout() {
  using namespace UmCardWidget;
  const float Px = GetPxPerSu();
  const bool bMini = IsMini(StateModel.Show);
  const FVector2D ShowSu = ShowSize(StateModel.Show, FaceKind == EUmCardFace::En);
  const float Band = BandOf(StateModel.Show);
  const bool bScan = (FaceKind != EUmCardFace::Fallback) && SrcPx.X > 0;
  FitNow = Fit(ShowSu, Band, bScan ? SrcPx : FIntPoint::ZeroValue, Px);
  if (Box) {
    Box->SetWidthOverride(ShowSu.X);
    Box->SetHeightOverride(ShowSu.Y);
  }
  if (Card) {
    Card->SetWidthOverride(FitNow.CardSu.X);
    Card->SetHeightOverride(FitNow.CardSu.Y);
  }
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Underlay) {
    // ВР-VS2-CP-07: card.navy under the whole card inside the keyline, radius r - 1 (procedural, no texture)
    const float R = Theme.RadiusSu(bMini ? TEXT("radius.s") : TEXT("radius.l"));
    Underlay->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), FMath::Max(0.0f, R - UnderlayInsetSu)));
  }
  const bool bFaceShown = bScan && FaceTexture && !bLoading;
  if (Face) {
    if (bFaceShown) {
      FSlateBrush Brush = Face->GetBrush();
      Brush.ImageSize = FitNow.ScanSu;
      Face->SetBrush(Brush);
    }
    Face->SetVisibility(bFaceShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  const bool bBackPlate = !bFaceShown && !bLoading && (FaceKind == EUmCardFace::Back || bMini);
  if (PlateIcon) PlateIcon->SetVisibility(bBackPlate ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (Fallback) {
    const bool bFallback = FaceKind == EUmCardFace::Fallback && !bMini && !bLoading;
    if (bFallback) ApplyFallbackContent();
    Fallback->SetVisibility(bFallback ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  ApplySpinner();
  // HB-25 (IC-34 П-2): the "+N" disc keeps >= 21 px on screen - 32 su below 1 px per su; 8 su of it on the frame
  // (ВР-VS3-09), centred or right-aligned (the attack boost, ВР-VS2-HB22-11) - VS-4 (VS-3 item 12): the right chip sits
  // on the drawn card's top-right corner (Card is the drawn rect, the cap included), 4 su in from its right edge; 4 su
  // over the edge it floated 20-25 px off the back at 720p 150 %
  const float Chip = ChipSuFor(Px);
  if (!FMath::IsNearlyEqual(Chip, ChipSuNow) || (BoostIcon && !FMath::IsNearlyEqual(BoostIcon->GetDisplaySizeSu(), Chip))) {
    ChipSuNow = Chip;
    if (BoostIcon) BoostIcon->SetDisplaySizeSu(Chip);
    if (BoostText) {
      FSlateFontInfo Font = UUmHudTheme::Get().Font(TEXT("type.tag"));
      Font.Size = UmHudTheme::PointsFromSu(12.0f * Chip / ChipSu);
      BoostText->SetFont(Font);
    }
  }
  if (BoostChip) {
    if (UOverlaySlot* S = Cast<UOverlaySlot>(BoostChip->Slot)) {
      S->SetHorizontalAlignment(bChipRightAbove ? HAlign_Right : HAlign_Center);
      S->SetPadding(FMargin(0.0f, -(ChipSuNow - ChipOnFrameSu), bChipRightAbove ? ChipCornerInsetSu : 0.0f, 0.0f));
    }
  }
}

void UUmCardWidget::SetChipRightAbove(bool bOn) {
  if (bOn == bChipRightAbove) return;
  bChipRightAbove = bOn;
  ApplyLayout();
}

void UUmCardWidget::SetOwnerOffset(const FVector2D& Su, float DurMs) {
  if (FMath::IsNearlyEqual(OffsetXTween.To, static_cast<float>(Su.X), 0.01f) &&
      FMath::IsNearlyEqual(OffsetYTween.To, static_cast<float>(Su.Y), 0.01f)) {
    return;
  }
  const double Now = NowMs();
  const float Ms = IsReduced() ? 0.0f : FMath::Max(0.0f, DurMs);
  StartTween(OffsetXTween, TweenValue(OffsetXTween, Now, true), static_cast<float>(Su.X), Ms);
  StartTween(OffsetYTween, TweenValue(OffsetYTween, Now, true), static_cast<float>(Su.Y), Ms);
  Step();
}

void UUmCardWidget::StartOwnerOffset(const FVector2D& From, const FVector2D& To, float DurMs, double DelayMs) {
  const float Ms = IsReduced() ? 0.0f : FMath::Max(0.0f, DurMs);
  StartTween(OffsetXTween, static_cast<float>(From.X), static_cast<float>(To.X), Ms);
  StartTween(OffsetYTween, static_cast<float>(From.Y), static_cast<float>(To.Y), Ms);
  if (Ms > 0.0f && DelayMs > 0.0) {
    OffsetXTween.StartMs += DelayMs;
    OffsetYTween.StartMs += DelayMs;
  }
  Step();
}

void UUmCardWidget::SetVisualHitTest(bool bOn) {
  // the drawn card (Card, under its render transform) registers in the hit test grid: the press, the hover and the
  // inspector reach the widget from the raised preview too; its layers stay hit-test invisible (Box and Stack only let
  // the pointer through to it)
  const ESlateVisibility Path = bOn ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::HitTestInvisible;
  if (Box) Box->SetVisibility(Path);
  if (UWidget* Stack = WidgetTree ? WidgetTree->FindWidget(FName(TEXT("Stack"))) : nullptr) Stack->SetVisibility(Path);
  if (Card) Card->SetVisibility(bOn ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible);
}

void UUmCardWidget::ApplyFrame() {
  using namespace UmCardWidget;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Px = GetPxPerSu();
  const bool bMini = IsMini(StateModel.Show);
  const float Radius = Theme.RadiusSu(bMini ? TEXT("radius.s") : TEXT("radius.l"));
  FrameKeyNow = FrameOverride.IsNone() ? FrameKey(bMini, bCandidate, bSelected, bHover && !bLowered) : FrameOverride;
  auto Brush = [&](FName Key, float R) {
    const FSlateBrush* B = Theme.CardFrameFor(Key, Px);
    return B ? *B : UmCardOutline(Key, R);
  };
  if (Frame) {
    const FSlateBrush* B = Theme.CardFrameFor(FrameKeyNow, Px);
    bFrameTexture = B && B->GetResourceObject() != nullptr;
    Frame->SetBrush(B ? *B : UmCardOutline(FrameKeyNow, Radius));
  }
  if (FlashLayer) FlashLayer->SetBrush(Brush(TEXT("card.frame.flash"), Radius));
  if (FocusRing) FocusRing->SetBrush(Brush(TEXT("card.frame.focus"), Radius + FocusOutsetSu));
  if (NewDot) {
    const FSlateBrush* B = Theme.CardFrameFor(TEXT("card.frame.new"), Px);
    if (B) {
      FSlateBrush Dot = *B;
      Dot.ImageSize = FVector2D(NewDotSu, NewDotSu);
      NewDot->SetBrush(Dot);
    } else {
      NewDot->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.glyph")), 0.5f * NewDotSu, Theme.Color(TEXT("mark.keyline")),
                                             1.0f, FVector2f(NewDotSu, NewDotSu)));
    }
  }
}

void UUmCardWidget::ApplyCursor() { SetCursor(bPlayable ? EMouseCursor::Hand : EMouseCursor::SlashedCircle); }

// ------------------------------------------------------------------------------------------------ states

void UUmCardWidget::StartTween(FTween& T, float From, float To, float DurMs) {
  T.StartMs = NowMs();
  T.From = From;
  T.To = To;
  T.DurMs = FMath::Max(0.0f, DurMs);
}

float UUmCardWidget::TweenValue(const FTween& T, double Now, bool bEaseOutQuad) const {
  if (T.StartMs < 0.0 || T.DurMs <= 0.0f) return T.To;
  const float A = FMath::Clamp(static_cast<float>((Now - T.StartMs) / T.DurMs), 0.0f, 1.0f);
  const float E = bEaseOutQuad ? S08IconMotion::Ease(ES08IconEase::EaseOutQuad, A) : A;
  return FMath::Lerp(T.From, T.To, E);
}

void UUmCardWidget::SetPlayable(bool bInPlayable, const FS09Reason& InReason) {
  Reason = bInPlayable ? FS09Reason() : InReason;
  if (bPlayable == bInPlayable) return;
  bPlayable = bInPlayable;
  const float Now = TweenValue(DesatTween, NowMs(), false);
  // CP-16: Desaturation 0 -> 0.6 and Opacity 1 -> 0.7 over hover.ms 150; reduced motion <= 100 ms (reduced.max_ms)
  const float Ms = IsReduced() ? UmCardWidget::ReducedMs : UUmHudTheme::Get().Ms(TEXT("hover.ms"));
  StartTween(DesatTween, Now, bPlayable ? 0.0f : 1.0f, Ms);
  ApplyCursor();
  Step();
}

FText UUmCardWidget::GetWhyText() const {
  // HB-24 (ВР-VS3-19): an unplayable card without an exact why.* key shows no tooltip
  if (bPlayable || !Reason.IsSet()) return FText::GetEmpty();
  const FS09Reason& R = Reason;
  FFormatNamedArguments Args;
  for (const TPair<FString, FString>& A : R.Args) Args.Add(A.Key, FText::FromString(A.Value));
  return Args.Num() ? UmText::Format(EUmTable::Why, R.Key.ToString(), Args) : UmText::Get(EUmTable::Why, R.Key.ToString());
}

void UUmCardWidget::SetNew(bool bOn) {
  if (bOn == bNew) return;
  bNew = bOn;
  if (bOn) {
    NewStartMs = NowMs();
    NewLeaveMs = -1.0;
  } else {
    NewLeaveMs = NowMs();
  }
  Step();
}

void UUmCardWidget::SetHover(bool bOn) {
  if (bOn == bHover) return;
  bHover = bOn;
  // CP-17: scale 1.5 over hover.ms ease-out-quad (pivot bottom centre), at most the 1.6 cap; reduced - no tween; the
  // lowered hand (SD-26) and the mini displays show no preview
  const bool bPreview = bOn && !bLowered && !UmCardWidget::IsMini(StateModel.Show);
  const float Target =
      bPreview ? UmCardWidget::HoverScaleFor(FitNow, UmCardWidget::CapScale, UmCardWidget::HoverScaleOf(StateModel.Show)) : 1.0f;
  StartTween(ScaleTween, ScaleNow, Target, IsReduced() ? 0.0f : UUmHudTheme::Get().Ms(TEXT("hover.ms")));
  ApplyFrame();
  Step();
}

void UUmCardWidget::SetSelected(bool bOn) {
  if (bOn == bSelected) return;
  bSelected = bOn;
  ApplyFrame();
}

void UUmCardWidget::SetFocus(bool bOn) {
  if (bOn == bFocus) return;
  bFocus = bOn;
  StartTween(FocusTween, GetFocusOpacity(), bOn ? 1.0f : 0.0f, UmCardWidget::FocusAppearMs);
  Step();
}

void UUmCardWidget::SetLowered(bool bOn) {
  if (bOn == bLowered) return;
  bLowered = bOn;
  if (bHover) {
    const bool bPreview = !bLowered && !UmCardWidget::IsMini(StateModel.Show);
    StartTween(ScaleTween, ScaleNow,
               bPreview ? UmCardWidget::HoverScaleFor(FitNow, UmCardWidget::CapScale, UmCardWidget::HoverScaleOf(StateModel.Show)) : 1.0f,
               IsReduced() ? 0.0f : UUmHudTheme::Get().Ms(TEXT("hover.ms")));
    ApplyFrame();
  }
  Step();
}

void UUmCardWidget::StartFlip(bool bToFace, float DurMs) {
  bFlipToFace = bToFace;
  bFlipSwapped = false;
  bFlipReduced = IsReduced();
  // reduced motion: a face cross-fade of 100 ms instead of the turn (CP-18, CP-20)
  FlipDurMs = bFlipReduced ? UmCardWidget::ReducedMs : DurMs;
  if (FlipDurMs <= 0.0f) {
    FlipStartMs = -1.0;
    DoSwap();
    return;
  }
  FlipStartMs = NowMs();
}

void UUmCardWidget::DoSwap() {
  bFlipSwapped = true;
  if (bFlipToFace) {
    // CP-20 privacy: the revealed face enters the widget in this frame (the card stands on its edge, nothing is drawn)
    if (PendingFace.IsSet()) {
      CardModel = PendingFace.GetValue();
      PendingFace.Reset();
      bRevealed = true;
    }
    bFaceDownNow = false;
  } else {
    bFaceDownNow = true;
  }
  ResolveFace();
  ApplyLayout();
}

void UUmCardWidget::SetFaceDown(bool bDown, float AnimMs) {
  if (bDown == bFaceDownNow && FlipStartMs < 0.0) return;
  StartFlip(!bDown, AnimMs);
  Step();
}

void UUmCardWidget::Flip(bool bToFace, float SpeedMul, const FS09CardView* InFace) {
  if (bToFace && InFace) {
    PendingFace = *InFace;
    // the texture loads during the first half of the turn, it is ASSIGNED only at the edge frame (DoSwap)
    if (!IsLegacy()) {
      const FString Lang = StateModel.Lang.IsEmpty() ? UmCardMedia::PreferredLang() : StateModel.Lang.ToLower();
      if (const FUmCardMediaEntry* E = UmCardMedia::FindCard(StateModel.HeroSlug, UmCardWidget::Slug(InFace->Name), Lang)) {
        const FSoftObjectPath Path(E->ObjectPath);
        if (bSyncLoad) {
          Path.TryLoad();
        } else if (!Path.ResolveObject()) {
          PreloadHandle = UAssetManager::GetStreamableManager().RequestAsyncLoad(Path, FStreamableDelegate());
        }
      }
    }
  }
  StartFlip(bToFace, UmCardWidget::RevealFlipMs * FMath::Max(0.0f, SpeedMul));
  Step();
}

void UUmCardWidget::SetBoostChip(int32 N) {
  if (N == Boost) return;
  const bool bWasShown = Boost != UmCardWidget::NoBoostChip;
  Boost = N;
  const double Now = NowMs();
  if (Boost == UmCardWidget::NoBoostChip) {
    if (bWasShown) ChipLeaveMs = Now;
  } else {
    // CP-18: the chip after the flip (150 - 330 ms); "+N" is runtime text (И-7), the opponent's chip has no number
    const double FlipEnd = FlipStartMs >= 0.0 ? FlipStartMs + FlipDurMs : Now;
    if (!bWasShown) ChipStartMs = FMath::Max(Now, FlipEnd);
    ChipLeaveMs = -1.0;
    if (BoostText) BoostText->SetText(FText::FromString(GetChipText()));
  }
  Step();
}

FString UUmCardWidget::GetChipText() const {
  if (Boost < 0) return FString();
  FFormatNamedArguments A;
  A.Add(TEXT("n"), FText::AsNumber(Boost));
  return UmText::Format(EUmTable::Hud, TEXT("hud.card.boost"), A).ToString();
}

void UUmCardWidget::SetDiscardCandidate(bool bOn) {
  if (bOn == bCandidate) return;
  bCandidate = bOn;
  ApplyFrame();
}

void UUmCardWidget::SetMarkedForDiscard(bool bOn) {
  if (bOn == bMarked) return;
  bMarked = bOn;
  // CP-19: 16 su down in 150 ms and card-drop 24 su; reduced motion - no shift tween, the icon by opacity <= 100 ms
  StartTween(ShiftTween, ShiftNow, bOn ? UmCardWidget::DiscardShiftSu : 0.0f, IsReduced() ? 0.0f : 150.0f);
  const double Now = NowMs();
  if (bOn) {
    DropStartMs = Now;
    DropLeaveMs = -1.0;
  } else {
    DropLeaveMs = Now;
  }
  Step();
}

void UUmCardWidget::PlayPlayedFlash(float SpeedScale) {
  FlashDurMs = UmCardWidget::PlayedFlashMs(SpeedScale, IsReduced());
  FlashStartMs = FlashDurMs > 0.0f ? NowMs() : -1.0;
  Step();
}

float UUmCardWidget::GetFlashOpacity() const {
  return FlashStartMs >= 0.0 ? UmCardWidget::FlashOpacity(static_cast<float>(NowMs() - FlashStartMs), FlashDurMs) : 0.0f;
}

// ------------------------------------------------------------------------------------------------ the step

double UUmCardWidget::AnimEndMs() const {
  double End = -1.0;
  for (const FTween* T : {&ScaleTween, &DesatTween, &ShiftTween, &FocusTween, &OffsetXTween, &OffsetYTween}) {
    if (T->StartMs >= 0.0) End = FMath::Max(End, T->StartMs + T->DurMs);
  }
  auto Pop = [&End](double Start, double Ms) {
    if (Start >= 0.0) End = FMath::Max(End, Start + Ms + 1.0);
  };
  Pop(NewStartMs, 180.0);
  Pop(NewLeaveMs, 120.0);
  Pop(ChipStartMs, 180.0);
  Pop(ChipLeaveMs, 120.0);
  Pop(DropStartMs, 180.0);
  Pop(DropLeaveMs, 120.0);
  Pop(FlashStartMs, FlashDurMs);
  return End;
}

bool UUmCardWidget::IsAnimating() const {
  const double Now = NowMs();
  // VS-3 frames step (ВР-VS3-69): a tween that ended between two frames still owes its end value - without this the
  // live client kept the last in-flight step (the CP-16 unplayable look stuck at desaturation 0.13 after a 100+ ms
  // frame, the attack-card raise at ~0.9)
  if (LastStepMs < AnimEndMs()) return true;
  auto Within = [Now](double Start, double Ms) { return Start >= 0.0 && Now < Start + Ms + 1.0; };
  return ScaleTween.IsRunning(Now) || DesatTween.IsRunning(Now) || ShiftTween.IsRunning(Now) ||
         FocusTween.IsRunning(Now) || OffsetXTween.IsRunning(Now) || OffsetYTween.IsRunning(Now) || FlipStartMs >= 0.0 || Within(NewStartMs, 180.0) || Within(NewLeaveMs, 120.0) ||
         Within(ChipStartMs, 180.0) || Within(ChipLeaveMs, 120.0) || Within(DropStartMs, 180.0) ||
         Within(DropLeaveMs, 120.0) || Within(FlashStartMs, FlashDurMs) || bLoading;
}

void UUmCardWidget::ApplySpinner() {
  // VS-3 HB-47 (04 §3.3): the scan's loader-spinner 32 su shows after 300 ms of loading, hides at once when ready
  if (!bLoading) SpinnerDelay.End();
  if (!Spinner) return;
  const bool bWant = bLoading && SpinnerDelay.IsShown(NowMs());
  const bool bWas = Spinner->GetVisibility() != ESlateVisibility::Collapsed;
  if (bWant == bWas) return;
  Spinner->SetVisibility(bWant ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (bWant) Spinner->PlayAnim(TEXT("cycle"));
}

void UUmCardWidget::Step() {
  using namespace UmCardWidget;
  const double Now = NowMs();
  LastStepMs = Now;  // ВР-VS3-69: IsAnimating owes one step past the end of every tween
  const bool bReduced = IsReduced();
  if (bLoading) ApplySpinner();
  // the flip (CP-18 / CP-20)
  ScaleXNow = 1.0f;
  float FaceFade = 1.0f;
  if (FlipStartMs >= 0.0) {
    const float T = static_cast<float>(Now - FlipStartMs);
    const float Half = 0.5f * FlipDurMs;
    if (!bFlipSwapped && T >= Half) DoSwap();
    if (T >= FlipDurMs) {
      FlipStartMs = -1.0;
    } else if (bFlipReduced) {
      FaceFade = T < Half ? 1.0f - T / Half : (T - Half) / Half;
    } else {
      ScaleXNow = FlipScaleX(T, FlipDurMs);
    }
  }
  ScaleNow = TweenValue(ScaleTween, Now, true);
  ShiftNow = TweenValue(ShiftTween, Now, true);
  OwnerOffsetNow = FVector2D(TweenValue(OffsetXTween, Now, true), TweenValue(OffsetYTween, Now, true));
  const float D = TweenValue(DesatTween, Now, false);
  DesatNow = D * UnplayableDesaturation;
  FaceOpacityNow = FMath::Lerp(1.0f, UnplayableOpacity, D) * FaceFade;
  if (FaceMid) {
    FaceMid->SetScalarParameterValue(ParamDesaturation, DesatNow);
    FaceMid->SetScalarParameterValue(ParamOpacity, FaceOpacityNow);
  } else if (Face) {
    Face->SetRenderOpacity(FaceOpacityNow);
  }
  if (Card) {
    const FWidgetTransform Want(FVector2D(OwnerOffsetNow.X, ShiftNow + OwnerOffsetNow.Y), FVector2D(ScaleNow * ScaleXNow, ScaleNow),
                                FVector2D::ZeroVector, 0.0f);
    const FWidgetTransform& Have = Card->GetRenderTransform();
    if (!Have.Translation.Equals(Want.Translation, 1.0e-3) || !Have.Scale.Equals(Want.Scale, 1.0e-4)) Card->SetRenderTransform(Want);
  }
  // an appear / leave pair on one widget (the dot, the chip, the drop icon): the curves of icon-motion.json; reduced -
  // opacity only, 100 ms
  auto Pop = [&](UWidget* W, double Start, double Leave, bool bOn) {
    if (!W) return;
    float Op = 0.0f;
    float Sc = 1.0f;
    if (Leave >= 0.0) {
      const float T = static_cast<float>(Now - Leave);
      Op = bReduced ? FMath::Clamp(1.0f - T / ReducedMs, 0.0f, 1.0f) : LeaveOpacity(T);
      Sc = bReduced ? 1.0f : LeaveScale(T);
    } else if (bOn && Start >= 0.0) {
      const float T = static_cast<float>(Now - Start);
      if (T < 0.0f) {
        Op = 0.0f;
      } else {
        Op = bReduced ? FMath::Clamp(T / ReducedMs, 0.0f, 1.0f) : AppearOpacity(T);
        Sc = bReduced ? 1.0f : AppearScale(T);
      }
    }
    const bool bShow = Op > 0.0f;
    W->SetVisibility(bShow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    W->SetRenderOpacity(Op);
    W->SetRenderTransformPivot(FVector2D(0.5, 0.5));
    W->SetRenderTransform(FWidgetTransform(FVector2D::ZeroVector, FVector2D(Sc, Sc), FVector2D::ZeroVector, 0.0f));
  };
  Pop(NewDot, NewStartMs, NewLeaveMs, bNew);
  Pop(BoostChip, ChipStartMs, ChipLeaveMs, Boost != NoBoostChip);
  if (BoostText) BoostText->SetVisibility(Boost >= 0 ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  Pop(DropIcon, DropStartMs, DropLeaveMs, bMarked);
  if (FocusRing) {
    const float Op = TweenValue(FocusTween, Now, false);
    FocusRing->SetVisibility(Op > 0.0f && !IsMini(StateModel.Show) ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    FocusRing->SetRenderOpacity(Op);
  }
  if (FlashLayer) {
    // CUE-006 (CP-21): the flash edge over idle, 1 -> 0 linear over FlashDurMs (500 x speed, reduced 100)
    float Op = 0.0f;
    if (FlashStartMs >= 0.0) {
      const float T = static_cast<float>(Now - FlashStartMs);
      Op = FlashOpacity(T, FlashDurMs);
      if (T >= FlashDurMs) FlashStartMs = -1.0;
    }
    FlashLayer->SetVisibility(Op > 0.0f && !IsMini(StateModel.Show) ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    FlashLayer->SetRenderOpacity(Op);
  }
  // the leave of a pop is over: forget it
  if (NewLeaveMs >= 0.0 && Now - NewLeaveMs >= 120.0) NewLeaveMs = -1.0, NewStartMs = -1.0;
  if (ChipLeaveMs >= 0.0 && Now - ChipLeaveMs >= 120.0) ChipLeaveMs = -1.0, ChipStartMs = -1.0;
  if (DropLeaveMs >= 0.0 && Now - DropLeaveMs >= 120.0) DropLeaveMs = -1.0, DropStartMs = -1.0;
}

void UUmCardWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (IsAnimating()) Step();
}

float UUmCardWidget::GetNewDotOpacity() const {
  return NewDot && NewDot->GetVisibility() != ESlateVisibility::Collapsed ? NewDot->GetRenderOpacity() : 0.0f;
}

float UUmCardWidget::GetChipOpacity() const {
  return BoostChip && BoostChip->GetVisibility() != ESlateVisibility::Collapsed ? BoostChip->GetRenderOpacity() : 0.0f;
}

float UUmCardWidget::GetDropOpacity() const {
  return DropIcon && DropIcon->GetVisibility() != ESlateVisibility::Collapsed ? DropIcon->GetRenderOpacity() : 0.0f;
}

float UUmCardWidget::GetFocusOpacity() const {
  return FocusRing && FocusRing->GetVisibility() != ESlateVisibility::Collapsed ? FocusRing->GetRenderOpacity() : 0.0f;
}

// ------------------------------------------------------------------------------------------------ trace

FString UUmCardWidget::StateText() const {
  TArray<FString> S;
  if (bFaceDownNow) S.Add(TEXT("back"));
  if (FlipStartMs >= 0.0) S.Add(TEXT("flipping"));
  if (bRevealed && !bFaceDownNow) S.Add(TEXT("reveal"));
  if (bHover) S.Add(bLowered ? TEXT("lowered") : TEXT("hover"));
  if (bSelected) S.Add(TEXT("selected"));
  if (bFocus) S.Add(TEXT("focus"));
  if (!bPlayable) S.Add(TEXT("unplayable"));
  if (bNew) S.Add(TEXT("new"));
  if (Boost != UmCardWidget::NoBoostChip) S.Add(TEXT("boost"));
  if (bCandidate) S.Add(TEXT("discard"));
  if (bMarked) S.Add(TEXT("marked"));
  if (FlashStartMs >= 0.0) S.Add(TEXT("flash"));
  if (bLoading) S.Add(TEXT("loading"));
  return S.Num() ? FString::Join(S, TEXT("+")) : FString(TEXT("idle"));
}

FString UUmCardWidget::ArtLine() const {
  const FString Tex = bLoading ? FString(TEXT("loading")) : TexPath;
  return UmCardWidget::TraceLine(FaceKey, FaceKind, Tex, StateModel.Show, FitNow, GetPxPerSu(), StateText(),
                                 Boost != UmCardWidget::NoBoostChip);
}

void UUmCardWidget::CollectShotLines(TArray<FString>& Out) const {
  if (bHasModel) Out.Add(ArtLine());
}

// ------------------------------------------------------------------------------------------------ input

void UUmCardWidget::SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                             const FS09OnHudPressOutcome& InOnOutcome) {
  PressId = InId;
  Arbiter = InArbiter;
  OnOutcome = InOnOutcome;
}

FReply UUmCardWidget::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton && OnInspect) return FReply::Handled();
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  // DE-014: the press belongs to the logical id (the instance id), the release decides (an unplayable card takes it too)
  Arbiter->Press(PressId, Arbiter->Now());
  FReply Reply = FReply::Handled();
  if (const TSharedPtr<SWidget> Cached = GetCachedWidget()) Reply.CaptureMouse(Cached.ToSharedRef());
  return Reply;
}

FReply UUmCardWidget::NativeOnMouseButtonDoubleClick(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (OnDoubleClick && InMouseEvent.GetEffectingButton() == EKeys::LeftMouseButton) {
    // HB-24 (UI-INP-003): the double click plays the card - the owner decides; no second press (its release is a
    // release without a press: nothing)
    OnDoubleClick();
    return FReply::Handled();
  }
  return NativeOnMouseButtonDown(InGeometry, InMouseEvent);
}

FReply UUmCardWidget::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton && OnInspect) {
    OnInspect();
    return FReply::Handled();
  }
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  // the drawn card counts too (HB-24: the raised preview of the hand, SetVisualHitTest)
  const FVector2D At = InMouseEvent.GetScreenSpacePosition();
  const bool bOver = InGeometry.IsUnderLocation(At) ||
                     (Card && Card->GetVisibility() == ESlateVisibility::Visible && Card->GetCachedGeometry().IsUnderLocation(At));
  const FS09HudPressOutcome Outcome = Arbiter->Release(bOver ? PressId : NAME_None, Arbiter->Now());
  if (Outcome.Result == ES09HudPressResult::Act || Outcome.Result == ES09HudPressResult::Refused) {
    // UI-INP-011: the answer in the frame of the release - an unplayable card is a refusal with its why.* (CUE-004)
    // HB-24 (ВР-VS3-19): without an exact why.* key the press goes on to the owner (the game logic answers it)
    FS09Reason Blocked;
    if (!bPlayable && Reason.IsSet()) Blocked = Reason;
    OnOutcome.ExecuteIfBound(FS09HudPressArbiter::Decide(Outcome, Blocked));
  }
  return FReply::Handled().ReleaseMouseCapture();
}

void UUmCardWidget::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  if (OnHoverChanged) OnHoverChanged(true);  // the owner lifts the card and orders it over the neighbours (HAND)
}

void UUmCardWidget::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  if (OnHoverChanged) OnHoverChanged(false);
}

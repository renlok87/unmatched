// VS-4 FX-38: the zone icons at a hovered space - see UmZoneBadges.h.
#include "UmZoneBadges.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"

namespace UmZoneBadges {
int32 L6SizePx(float RadiusPx) {
  return FMath::Clamp(FMath::RoundToInt(L6Ratio * 2.0f * RadiusPx), L6MinPx, L6MaxPx);
}

int32 TexturePxFor(int32 L6Px) {
  if (L6Px < MinShowL6Px) return 0;
  const int32 Want = FMath::Max(L6Px, MinIconPx);  // ВР-VS4-56: 720p K1 (L6 20...23) shows the 24 px export
  static const int32 Sizes[] = {24, 32, 36, 48, 64};
  int32 Best = Sizes[0];
  for (const int32 S : Sizes) {
    if (FMath::Abs(S - Want) <= FMath::Abs(Best - Want)) Best = S;  // a tie - the larger
  }
  return Best;
}

double Contrast(const FLinearColor& A, const FLinearColor& B) {
  // WCAG relative luminance of the linear colours (FLinearColor holds linear RGB)
  auto L = [](const FLinearColor& C) { return 0.2126 * C.R + 0.7152 * C.G + 0.0722 * C.B; };
  const double X = L(A), Y = L(B);
  return (FMath::Max(X, Y) + 0.05) / (FMath::Min(X, Y) + 0.05);
}

FLinearColor InkFor(const FColor& Disc, bool* bOutNavy) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const FLinearColor D = FLinearColor::FromSRGBColor(Disc);
  const FLinearColor Navy = Theme.Color(TEXT("card.navy"));
  const FLinearColor Glyph = Theme.Color(TEXT("card.glyph"));
  const bool bNavy = Contrast(Navy, D) >= Contrast(Glyph, D);
  if (bOutNavy) *bOutNavy = bNavy;
  return bNavy ? Navy : Glyph;
}

FUmZonePlan Plan(const FUmZoneBadgeInput& In) {
  FUmZonePlan P;
  P.L6Px = L6SizePx(In.RadiusPx);
  if (!In.bShow) {
    P.Hidden = TEXT("off");
    return P;
  }
  // the keys with a disc colour on this board (a key the profile does not know shows nothing - never the topology hex)
  TArray<FName> Keys;
  for (const FName& K : In.Keys) {
    FColor C;
    if (In.DiscColor && In.DiscColor(K, C)) Keys.AddUnique(K);
  }
  if (In.Keys.Num() == 0) {
    P.Hidden = TEXT("nokeys");
    return P;
  }
  if (Keys.Num() == 0) {
    P.Hidden = TEXT("nocolor");
    return P;
  }
  P.TexturePx = TexturePxFor(P.L6Px);
  if (P.TexturePx == 0) {
    P.Hidden = TEXT("small");  // HI-12 / ВР-VS4-56: L6 below 20 px (minimum zoom) - no zone icon
    return P;
  }
  const int32 Icons = Keys.Num() > MaxIcons ? MaxIcons - 1 : Keys.Num();
  for (int32 I = 0; I < Icons; ++I) P.Shown.Add(Keys[I]);
  P.More = Keys.Num() > MaxIcons ? Keys.Num() - Icons : 0;
  const int32 Cells = Icons + (P.More > 0 ? 1 : 0);
  const float S = static_cast<float>(P.TexturePx);
  const float H = Cells * S + (Cells - 1) * GapPx;
  const float AX = FMath::RoundToFloat(In.CentrePx.X + In.AnchorPx - 0.5f * S);
  const float AY = FMath::RoundToFloat(In.CentrePx.Y - 0.5f * H);
  // never over a figure or its tag (MS-R-72 / FX-38 dont): the right anchor first; else the nearest of the places right of
  // a covered rect and above / below a covered rect (and their combinations) - the least covered, then the nearest
  auto Covered = [&In](float X, float Y, float W, float Hh) {
    const FS08ScreenRect C(X, Y, X + W, Y + Hh);
    double A = 0.0;
    for (const FS08ScreenRect& R : In.Avoid) A += R.IsEmpty() ? 0.0 : C.IntersectionArea(R);
    return A;
  };
  TArray<float> Xs = {AX};
  TArray<float> Ys = {AY};
  for (const FS08ScreenRect& R : In.Avoid) {
    if (R.IsEmpty()) continue;
    Xs.Add(FMath::CeilToFloat(R.X1 + GapPx));
    Ys.Add(FMath::FloorToFloat(R.Y0 - GapPx - H));
    Ys.Add(FMath::CeilToFloat(R.Y1 + GapPx));
  }
  float X0 = AX, Y0 = AY;
  double Best = Covered(AX, AY, S, H), BestDist = 0.0;
  if (Best > 0.0) {
    for (const float X : Xs) {
      for (const float Y : Ys) {
        if (X < AX || X + S > In.ViewportPx.X || Y < 0.0f || Y + H > In.ViewportPx.Y) continue;  // right of the anchor only
        const double A = Covered(X, Y, S, H);
        const double D = FVector2D::Distance(FVector2D(X, Y), FVector2D(AX, AY));
        if (A < Best || (A == Best && D < BestDist)) {
          Best = A;
          BestDist = D;
          X0 = X;
          Y0 = Y;
        }
      }
    }
    P.bMoved = X0 != AX || Y0 != AY;
  }
  X0 = FMath::Min(X0, static_cast<float>(In.ViewportPx.X) - S);
  P.Column = FS08ScreenRect(X0, Y0, X0 + S, Y0 + H);
  for (const FS08ScreenRect& R : In.Avoid) P.Overlap += R.IsEmpty() ? 0.0 : P.Column.IntersectionArea(R);
  for (int32 I = 0; I < Cells; ++I) {
    const float Y = Y0 + I * (S + GapPx);
    const FS08ScreenRect R(X0, Y, X0 + S, Y + S);
    if (I < Icons) {
      P.IconRects.Add(R);
    } else {
      P.MoreRect = R;
    }
  }
  return P;
}
}  // namespace UmZoneBadges

bool UUmZoneBadges::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    MorePlate = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("MorePlate")));
    MorePlate->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), Theme.RadiusSu(TEXT("radius.s")),
                                              Theme.Color(TEXT("mark.keyline")), 1.0f));
    MorePlate->SetHorizontalAlignment(HAlign_Center);
    MorePlate->SetVerticalAlignment(VAlign_Center);
    MorePlate->SetPadding(FMargin(0.0f));
    MorePlate->SetVisibility(ESlateVisibility::Collapsed);
    MoreText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("MoreText")));
    MoreText->SetFont(Theme.Font(TEXT("type.tag")));
    MoreText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.cream"))));
    MoreText->SetShadowOffset(FVector2D::ZeroVector);
    MorePlate->SetContent(MoreText);
    Root->AddChildToCanvas(MorePlate);
  }
  if (bFirst) SetVisibility(ESlateVisibility::HitTestInvisible);  // the board takes the pointer
  return bFirst;
}

US08AnimatedIconWidget* UUmZoneBadges::IconAt(int32 Set, int32 Index) {
  const int32 I = Set * UmZoneBadges::MaxIcons + Index;
  while (Icons.Num() <= I) {
    US08AnimatedIconWidget* W = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
    if (!W) return nullptr;
    W->SetVisibility(ESlateVisibility::Collapsed);
    if (Root) Root->AddChildToCanvas(W);
    Icons.Add(W);
  }
  return Icons[I];
}

void UUmZoneBadges::Place(UWidget* W, const FS08ScreenRect& RectPx, int32 Z) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(FVector2D(RectPx.X0, RectPx.Y0) / Ppu);
    S->SetSize(FVector2D(RectPx.Width(), RectPx.Height()) / Ppu);
    S->SetZOrder(Z);
  }
}

bool UUmZoneBadges::GetShownColors(FName Key, FLinearColor& OutDisc, FLinearColor& OutInk) const {
  const FLinearColor* D = DiscNow.Find(Key);
  const FLinearColor* I = InkNow.Find(Key);
  if (!D || !I) return false;
  OutDisc = *D;
  OutInk = *I;
  return true;
}

void UUmZoneBadges::ApplyInput(const FUmZoneBadgeInput& In) {
  const FUmZonePlan P = UmZoneBadges::Plan(In);
  FString Sig = FString::Printf(TEXT("%s|%d|%d|%s|%.0f,%.0f|"), In.bShow ? *In.SpaceId : TEXT("-"), P.TexturePx, P.More, *P.Hidden,
                                P.Column.X0, P.Column.Y0);
  for (const FName& K : P.Shown) {
    FColor C;
    if (In.DiscColor && In.DiscColor(K, C)) Sig += K.ToString() + C.ToHex();
  }
  if (Sig == Signature) return;
  Signature = Sig;
  ++ApplyCount;
  const bool bReduced = ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
  const FString NewSpace = P.Hidden.IsEmpty() ? In.SpaceId : FString();
  const bool bNewSet = NewSpace != SpaceNow || P.TexturePx != PlanNow.TexturePx || P.Shown != PlanNow.Shown;
  if (bNewSet) {
    // the old icons leave and the new ones appear in one frame (FX-38 timing)
    for (int32 I = 0; I < UmZoneBadges::MaxIcons; ++I) {
      US08AnimatedIconWidget* Old = IconAt(SetNow, I);
      if (Old && Old->GetVisibility() != ESlateVisibility::Collapsed) Old->PlayAnim(FName(TEXT("leave")));
    }
    SetNow = 1 - SetNow;
  }
  DiscNow.Reset();
  InkNow.Reset();
  for (int32 I = 0; I < UmZoneBadges::MaxIcons; ++I) {
    US08AnimatedIconWidget* W = IconAt(SetNow, I);
    if (!W) continue;
    if (!P.Shown.IsValidIndex(I)) {
      if (bNewSet) W->SetVisibility(ESlateVisibility::Collapsed);
      continue;
    }
    const FName Key = P.Shown[I];
    FColor Disc = FColor::White;
    if (In.DiscColor) In.DiscColor(Key, Disc);
    const FLinearColor DiscLin = FLinearColor::FromSRGBColor(Disc);
    const FLinearColor Ink = UmZoneBadges::InkFor(Disc);
    DiscNow.Add(Key, DiscLin);
    InkNow.Add(Key, Ink);
    if (bNewSet) {
      W->SetReducedMotion(bReduced);
      W->SetIcon(FName(*(TEXT("zone-") + Key.ToString())), static_cast<float>(P.TexturePx) / Ppu, P.TexturePx);
    }
    W->SetTint(FName(TEXT("zone")), DiscLin);
    W->SetTint(FName(TEXT("ink")), Ink);
    Place(W, P.IconRects[I], 10 + I);
    W->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (bNewSet) W->PlayAnim(FName(TEXT("appear")));
  }
  if (MorePlate && MoreText) {
    MorePlate->SetVisibility(P.More > 0 ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    if (P.More > 0) {
      MoreText->SetText(FText::FromString(FString::Printf(TEXT("+%d"), P.More)));
      Place(MorePlate, P.MoreRect, 20);
    }
  }
  PlanNow = P;
  SpaceNow = NewSpace;
}

void UUmZoneBadges::CollectShotLines(TArray<FString>& Out) const {
  const bool bShown = PlanNow.Hidden.IsEmpty() && PlanNow.Shown.Num() > 0;
  TArray<FString> Keys;
  for (const FName& K : PlanNow.Shown) Keys.Add(K.ToString());
  const FString Extra = FString::Printf(TEXT("space=%s keys=%s shown=%d more=%d px=%d tex=%d moved=%d overlap=%.0f hidden=%s"),
                                        SpaceNow.IsEmpty() ? TEXT("none") : *SpaceNow, Keys.Num() ? *FString::Join(Keys, TEXT(",")) : TEXT("-"),
                                        PlanNow.Shown.Num(), PlanNow.More, PlanNow.L6Px, PlanNow.TexturePx, PlanNow.bMoved ? 1 : 0,
                                        PlanNow.Overlap, PlanNow.Hidden.IsEmpty() ? TEXT("-") : *PlanNow.Hidden);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("zone"), TEXT("umg"), bShown ? TEXT("shown") : TEXT("hidden"), FString(), PlanNow.Column,
                                        bShown && !PlanNow.Column.IsEmpty(), bShown, TEXT("UUmZoneBadges"), Extra));
}

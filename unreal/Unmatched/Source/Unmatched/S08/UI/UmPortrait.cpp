// VS-2 CP-08: the portrait circle helpers - see UmPortrait.h.
#include "UmPortrait.h"

#include "UmCardMedia.h"
#include "UmHudTheme.h"
#include "../S08HudTokens.generated.h"
#include "../../S09/S09TurnHud.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace UmPortrait {
FString SlugOf(const FString& Name) {
  FString Out;
  for (const TCHAR C : Name.ToLower()) {
    if ((C >= TEXT('a') && C <= TEXT('z')) || (C >= TEXT('0') && C <= TEXT('9')) || C == TEXT('-')) {
      Out.AppendChar(C);
    } else if (C == TEXT(' ') || C == TEXT('_')) {
      Out.AppendChar(TEXT('-'));
    }
  }
  return Out;
}

bool IsSidekickKey(FName Key) { return Key.ToString().Contains(TEXT("/")); }

const FUmCardMediaEntry* Find(FName Key) {
  if (Key.IsNone()) return nullptr;
  FString Hero = Key.ToString();
  FString Sidekick;
  if (Hero.Split(TEXT("/"), &Hero, &Sidekick)) return UmCardMedia::FindPortrait(Hero, Sidekick);
  return UmCardMedia::FindPortrait(Hero);
}

FString FallbackText(FName Key, const FString& Name, int32 SidekickNumber) {
  // ВР-CP09 / ВР-07: a harpy is its number, never the "H" of Monogram("Harpies")
  if (Key.ToString().EndsWith(TEXT("/harpies")) && SidekickNumber >= 1 && SidekickNumber <= 3) {
    return FString::FromInt(SidekickNumber);
  }
  return S09TurnHud::Monogram(Name);
}

float SourceCirclePx(const FUmCardMediaEntry& Entry) {
  return Entry.bHasDisc ? static_cast<float>(Entry.Disc.Z * Entry.Src.X) : static_cast<float>(Entry.Src.X);
}

FVector4 UvRect(const FUmCardMediaEntry& Entry) {
  const FVector Disc = Entry.bHasDisc ? Entry.Disc : FVector(0.5, 0.5, 1.0);
  const double R = 0.5 * Disc.Z;
  return FVector4((Disc.X - R) * Entry.Uv.X, (Disc.Y - R) * Entry.Uv.Y, (Disc.X + R) * Entry.Uv.X,
                  (Disc.Y + R) * Entry.Uv.Y);
}

float CappedSu(float ShowSu, float SrcCirclePx, float PxPerSu) {
  if (SrcCirclePx <= 0.0f || PxPerSu <= 0.0f) return ShowSu;
  return FMath::Min(ShowSu, CapScale * SrcCirclePx / PxPerSu);
}

float Desaturation(EUmPortraitState State) { return State == EUmPortraitState::Avatar ? 0.0f : 1.0f; }

float Opacity(EUmPortraitState State) { return State == EUmPortraitState::Loser ? LoserOpacity : 1.0f; }

const TCHAR* StateName(EUmPortraitState State) {
  switch (State) {
    case EUmPortraitState::Fallen: return TEXT("fallen");
    case EUmPortraitState::Loser: return TEXT("loser");
    default: return TEXT("avatar");
  }
}

void SetupDiscMid(UMaterialInstanceDynamic& Mid, const FUmCardMediaEntry& Entry, UTexture2D* Tex, float CircleSu) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Mid.SetTextureParameterValue(ParamAvatar, Tex);
  const FVector4 R = UvRect(Entry);
  Mid.SetVectorParameterValue(ParamUvRect, FLinearColor(R.X, R.Y, R.Z, R.W));
  FLinearColor Edge = Theme.Color(TEXT("panel.edge"));
  Edge.A = S08HudTokens::Alpha_PanelEdge;  // the rim keeps the token's alpha over panel.bg (4.0 : 1)
  Mid.SetVectorParameterValue(ParamEdgeColor, Edge);
  Mid.SetVectorParameterValue(ParamKeylineColor, Theme.Color(TEXT("mark.keyline")));
  Mid.SetVectorParameterValue(ParamFillColor, Theme.Color(TEXT("card.navy")));
  Mid.SetScalarParameterValue(ParamEdgeFrac, EdgeSu / FMath::Max(CircleSu, 1.0f));
  Mid.SetScalarParameterValue(ParamKeylineFrac, KeylineSu / FMath::Max(CircleSu, 1.0f));
}

FString TraceLine(FName Key, const FString& Texture, float Su, float PxPerSu, float SrcCirclePx, const TCHAR* Show,
                  const TCHAR* Side, EUmPortraitState State, float ShowSu, int32 Number) {
  const float Px = Su * PxPerSu;
  const bool bAvatar = Texture.StartsWith(TEXT("/"));
  const float Scale = SrcCirclePx > 0.0f && bAvatar ? Px / SrcCirclePx : 0.0f;
  const bool bCapped = bAvatar && ShowSu > 0.0f && Su < ShowSu - 0.05f;
  FString Line = FString::Printf(TEXT("PORTRAIT id=%s tex=%s su=%.1f px=%.1f scale=%.3f show=%s side=%s state=%s capped=%d"),
                                 Key.IsNone() ? TEXT("none") : *Key.ToString(), Texture.IsEmpty() ? TEXT("monogram") : *Texture,
                                 Su, Px, Scale, Show, Side, StateName(State), bCapped ? 1 : 0);
  if (Number > 0) Line += FString::Printf(TEXT(" n=%d"), Number);
  return Line;
}

UWidget* MakeDisc(UWidgetTree& Tree, UObject* Outer, const FUmPortraitDiscSpec& Spec, FUmPortraitShown& Out,
                  TArray<TObjectPtr<UObject>>& KeepAlive) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Out = FUmPortraitShown();
  Out.Key = Spec.Key;
  Out.ShowSu = Spec.ShowSu;
  Out.PxPerSu = Spec.PxPerSu > 0.0f ? Spec.PxPerSu : 1.0f;
  Out.State = Spec.State;
  Out.Number = Spec.Number;
  USizeBox* Box = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass());
  Box->SetWidthOverride(Spec.ShowSu);
  Box->SetHeightOverride(Spec.ShowSu);
  const FUmCardMediaEntry* Entry = Spec.bLegacy ? nullptr : Find(Spec.Key);
  UTexture2D* Tex = Entry ? UmCardMedia::LoadTexture(*Entry) : nullptr;
  UMaterialInterface* Mat = Tex ? LoadObject<UMaterialInterface>(nullptr, MaterialPath, nullptr, LOAD_NoWarn | LOAD_Quiet) : nullptr;
  if (Entry) Out.SrcPx = SourceCirclePx(*Entry);
  if (Tex && Mat) {
    // the avatar: the registry disc of the accepted CP-07 crop, at most 1.6x the source circle (ВР-CP04), centred
    Out.Su = CappedSu(Spec.ShowSu, Out.SrcPx, Out.PxPerSu);
    Out.Tex = Entry->ObjectPath;
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Mat, Outer);
    SetupDiscMid(*Mid, *Entry, Tex, Out.Su);
    Mid->SetScalarParameterValue(ParamDesaturation, Desaturation(Spec.State));
    Mid->SetScalarParameterValue(ParamOpacity, Opacity(Spec.State));
    KeepAlive.Add(Mid);
    UImage* Image = Tree.ConstructWidget<UImage>(UImage::StaticClass());
    FSlateBrush Brush;
    Brush.SetResourceObject(Mid);
    Brush.ImageSize = FVector2D(Out.Su, Out.Su);
    Image->SetBrush(Brush);
    if (USizeBoxSlot* S = Cast<USizeBoxSlot>(Box->AddChild(Image))) {
      S->SetHorizontalAlignment(HAlign_Center);
      S->SetVerticalAlignment(VAlign_Center);
    }
    return Box;
  }
  // 02 §6.4: the monogram only as the fallback (CP-08); a harpy is its number, never "H" (ВР-CP09)
  Out.Su = Spec.ShowSu;
  Out.Tex = Spec.bLegacy ? TEXT("legacy") : TEXT("monogram");
  if (!Spec.bLegacy) {
    UE_LOG(LogTemp, Warning, TEXT("PORTRAIT fallback id=%s reason=%s su=%.0f"), Spec.Key.IsNone() ? TEXT("none") : *Spec.Key.ToString(),
           !Entry ? TEXT("no-registry-entry") : !Tex ? TEXT("texture-missing") : TEXT("material-missing"), Spec.ShowSu);
  }
  UOverlay* Stack = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass());
  UImage* Disc = Tree.ConstructWidget<UImage>(UImage::StaticClass());
  Disc->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), 0.5f * Spec.ShowSu, FVector2f(Spec.ShowSu, Spec.ShowSu)));
  if (UOverlaySlot* D = Stack->AddChildToOverlay(Disc)) {
    // the disc and its text share one centre even when a parent stretches the box (a gallery column)
    D->SetHorizontalAlignment(HAlign_Center);
    D->SetVerticalAlignment(VAlign_Center);
  }
  UTextBlock* Mono = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  // CP-07: the monogram cap min(24, 0.38 D) su - type.tag (cap 10) up to the 40 su circles, type.heading (cap 17) above
  Mono->SetFont(Theme.Font(Spec.ShowSu < 48.0f ? TEXT("type.tag") : TEXT("type.heading")));
  Mono->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  Mono->SetText(FText::FromString(FallbackText(Spec.Key, Spec.Name, Spec.Number)));
  if (UOverlaySlot* M = Stack->AddChildToOverlay(Mono)) {
    M->SetHorizontalAlignment(HAlign_Center);
    M->SetVerticalAlignment(VAlign_Center);
  }
  Stack->SetRenderOpacity(Opacity(Spec.State));
  Box->SetContent(Stack);
  return Box;
}

UWidget* MakeNumberBadge(UWidgetTree& Tree, int32 Number) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UOverlay* Badge = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass());
  UImage* Disc = Tree.ConstructWidget<UImage>(UImage::StaticClass());
  // 02 §6.5: the card.navy disc with the mark.keyline (Slate draws the outline inside the 14 su)
  Disc->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), 0.5f * BadgeSu, Theme.Color(TEXT("mark.keyline")),
                                       BadgeKeylineSu, FVector2f(BadgeSu, BadgeSu)));
  Badge->AddChildToOverlay(Disc);
  UTextBlock* Digit = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  Digit->SetFont(Theme.Font(TEXT("type.tag")));
  Digit->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.cream"))));
  Digit->SetText(FText::AsNumber(Number));
  if (UOverlaySlot* D = Badge->AddChildToOverlay(Digit)) {
    D->SetHorizontalAlignment(HAlign_Center);
    D->SetVerticalAlignment(VAlign_Center);
  }
  return Badge;
}
}  // namespace UmPortrait

FString FUmPortraitShown::Line(const TCHAR* Show, const TCHAR* Side) const {
  return UmPortrait::TraceLine(Key, Tex, Su, PxPerSu, SrcPx, Show, Side, State, ShowSu, Number);
}

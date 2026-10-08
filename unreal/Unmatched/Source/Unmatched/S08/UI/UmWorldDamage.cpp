// VS-6 F2 FX-22 / IC-49: the «−N» / «+N» numbers over a figure - see UmWorldDamage.h.
#include "UmWorldDamage.h"

#include "../Fx/S08CombatFx.h"
#include "../S08ArtLook.h"
#include "../S08IconMotion.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "HAL/PlatformTime.h"

namespace UmWorldDamage {
bool DamageV2() { return !S08ArtLook::SlateHudBlocks().IsSlate(FName(TEXT("damage"))); }

FText NumberText(int32 Amount) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("n"), FText::AsNumber(FMath::Abs(Amount)));
  return UmText::Format(EUmTable::Hud, Amount < 0 ? TEXT("hud.damage.plus") : TEXT("hud.damage.minus"), Args);
}

bool AboveFigure(const FS08ScreenRect& Figure, const FVector2D& SizePx, const FVector2D& ViewportPx,
                 const TArray<FS08ScreenRect>& Hard, FS08ScreenRect& Out) {
  if (Figure.IsEmpty() || SizePx.X <= 0.0 || SizePx.Y <= 0.0) return false;
  const float W = static_cast<float>(SizePx.X);
  const float H = static_cast<float>(SizePx.Y);
  const float Cx = Figure.Center().X;
  FS08ScreenRect R(FMath::RoundToFloat(Cx - 0.5f * W), FMath::RoundToFloat(Figure.Y0 - GapPx - H), 0.0f, 0.0f);
  R.X1 = R.X0 + W;
  R.Y1 = R.Y0 + H;
  if (R.X0 < 0.0f || R.Y0 < 0.0f || R.X1 > ViewportPx.X || R.Y1 > ViewportPx.Y) return false;
  for (const FS08ScreenRect& Box : Hard) {
    if (R.IntersectionArea(Box) > 0.0) return false;
  }
  Out = R;
  return true;
}

FString LookField() {
  return FString::Printf(TEXT("damage=%s"), DamageV2() ? TEXT("v2") : TEXT("legacy(-S08SlateHud=damage)"));
}
}  // namespace UmWorldDamage

bool UUmWorldDamage::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree || WidgetTree->RootWidget) return bFirst;
  Root = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), TEXT("Numbers"));
  WidgetTree->RootWidget = Root;
  for (int32 I = 0; I < S08CombatFx::MaxNumbers; ++I) BuildSlot(I);
  Entries.SetNum(S08CombatFx::MaxNumbers);
  return bFirst;
}

void UUmWorldDamage::BuildSlot(int32 Index) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UWidgetTree& Tree = *WidgetTree;
  UBorder* Capsule = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), *FString::Printf(TEXT("Capsule%d"), Index));
  Capsule->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), Theme.RadiusSu(TEXT("radius.s")),
                                          Theme.Color(TEXT("panel.edge")), 1.0f));
  Capsule->SetPadding(FMargin(UmWorldDamage::PadXSu, UmWorldDamage::PadYSu));
  Capsule->SetHorizontalAlignment(HAlign_Center);
  Capsule->SetVerticalAlignment(VAlign_Center);
  Capsule->SetVisibility(ESlateVisibility::Collapsed);
  Capsule->SetRenderTransformPivot(FVector2D(0.5f, 1.0f));
  if (UOverlaySlot* S = Root->AddChildToOverlay(Capsule)) {
    S->SetHorizontalAlignment(HAlign_Center);
    S->SetVerticalAlignment(VAlign_Bottom);
  }
  UHorizontalBox* Row = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(),
                                                             *FString::Printf(TEXT("Row%d"), Index));
  Capsule->SetContent(Row);
  UImage* Icon = Tree.ConstructWidget<UImage>(UImage::StaticClass(), *FString::Printf(TEXT("HealIcon%d"), Index));
  Icon->SetVisibility(ESlateVisibility::Collapsed);
  if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Icon)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetPadding(FMargin(0.0f, 0.0f, 4.0f, 0.0f));
  }
  UTextBlock* Text = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), *FString::Printf(TEXT("Text%d"), Index));
  Text->SetFont(Theme.Font(TEXT("type.damage")));
  Text->SetShadowOffset(FVector2D::ZeroVector);
  if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Text)) S->SetVerticalAlignment(VAlign_Center);
  Capsules.Add(Capsule);
  Texts.Add(Text);
  Icons.Add(Icon);
}

void UUmWorldDamage::Clear() {
  for (int32 I = 0; I < Entries.Num(); ++I) {
    Entries[I] = FEntry();
    if (Capsules.IsValidIndex(I) && Capsules[I]) Capsules[I]->SetVisibility(ESlateVisibility::Collapsed);
  }
  Newest = INDEX_NONE;
}

double UUmWorldDamage::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

void UUmWorldDamage::EnsureHealBrush() {
  if (bHealBrush) return;
  bHealBrush = true;
  // IC-49: the export for 24 su at this DPI x UI scale (18 at 720p, 36 at 150 %); the 1024 master is never scaled
  const int32 Px = S08IconMotion::ExportSizePx(UmWorldDamage::HealIconSu, UmHudScale::Current().PxPerSu());
  HealTexture = LoadObject<UTexture2D>(nullptr, *S08IconMotion::TextureObjectPath(TEXT("state-heal"), -1, Px));
  if (!HealTexture) {
    UE_LOG(LogTemp, Warning, TEXT("UMWORLD damage: state-heal %d px missing (the «+N» shows without its icon)"), Px);
    return;
  }
  HealBrush.SetResourceObject(HealTexture);
  HealBrush.DrawAs = ESlateBrushDrawType::Image;
  HealBrush.ImageSize = FVector2D(UmWorldDamage::HealIconSu, UmWorldDamage::HealIconSu);
  HealBrush.TintColor = FSlateColor(FLinearColor::White);
}

void UUmWorldDamage::Push(const FString& InFighterId, int32 Amount, int32 Seq, int32 LifeMs, bool bReduced) {
  if (!Root || Amount == 0) return;
  if (InFighterId != FighterId) {
    for (FEntry& E : Entries) E = FEntry();
    FighterId = InFighterId;
  }
  for (const FEntry& E : Entries) {
    if (E.bShown && E.Seq == Seq && (E.Amount < 0) == (Amount < 0)) return;  // the same number again (a relayout)
  }
  Step();  // drop the finished ones first
  int32 Free = INDEX_NONE;
  int32 Oldest = INDEX_NONE;
  float TopSu = -1.0f;  // the highest number shown now (its base + its rise), -1 = none
  const double NowS = Now();
  for (int32 I = 0; I < Entries.Num(); ++I) {
    if (!Entries[I].bShown) {
      if (Free == INDEX_NONE) Free = I;
      continue;
    }
    const FEntry& O = Entries[I];
    const float Rise = S08CombatFx::NumberPose((NowS - O.StartS) * 1000.0, O.LifeMs, O.bReduced).RiseSu;
    TopSu = FMath::Max(TopSu, O.BaseSu + Rise);
    if (Oldest == INDEX_NONE || Entries[I].StartS < Entries[Oldest].StartS) Oldest = I;
  }
  const int32 Use = Free != INDEX_NONE ? Free : Oldest;  // at most four: the oldest gives way
  Texts[Use]->SetText(UmWorldDamage::NumberText(Amount));  // measured with its own text
  Capsules[Use]->ForceLayoutPrepass();
  const float CapsuleSu = static_cast<float>(Capsules[Use]->GetDesiredSize().Y);
  const float StepSu = FMath::Max(S08CombatFx::NumberStackSu, CapsuleSu + 4.0f);
  FEntry& E = Entries[Use];
  E.Amount = Amount;
  E.Seq = Seq;
  E.BaseSu = TopSu < 0.0f ? 0.0f : TopSu + StepSu;
  E.StartS = Now();
  E.LifeMs = LifeMs;
  E.bReduced = bReduced;
  E.bShown = true;
  Newest = Use;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Texts[Use]->SetText(UmWorldDamage::NumberText(Amount));
  Texts[Use]->SetColorAndOpacity(FSlateColor(Theme.Color(Amount < 0 ? TEXT("fx.heal") : TEXT("damage.text"))));
  const bool bIcon = Amount < 0 && bReduced;  // IC-49: only when the heal motes are off (reduced motion)
  if (bIcon) EnsureHealBrush();
  if (bIcon && HealTexture) {
    Icons[Use]->SetBrush(HealBrush);
    Icons[Use]->SetVisibility(ESlateVisibility::HitTestInvisible);
  } else {
    Icons[Use]->SetVisibility(ESlateVisibility::Collapsed);
  }
  Capsules[Use]->SetVisibility(ESlateVisibility::HitTestInvisible);
  ApplyEntry(Use, E);
}

void UUmWorldDamage::ApplyEntry(int32 Index, const FEntry& E) {
  const double Ms = (Now() - E.StartS) * 1000.0;
  const S08CombatFx::FNumberPose P = S08CombatFx::NumberPose(Ms, E.LifeMs, E.bReduced);
  FWidgetTransform T;
  T.Translation = FVector2D(0.0, -(P.RiseSu + E.BaseSu));
  T.Scale = FVector2D(P.Scale, P.Scale);
  Capsules[Index]->SetRenderTransform(T);
  Capsules[Index]->SetRenderOpacity(P.Opacity);
}

void UUmWorldDamage::Step() {
  const double NowS = Now();
  for (int32 I = 0; I < Entries.Num(); ++I) {
    FEntry& E = Entries[I];
    if (!E.bShown) continue;
    if ((NowS - E.StartS) * 1000.0 >= E.LifeMs) {
      E.bShown = false;
      Capsules[I]->SetVisibility(ESlateVisibility::Collapsed);
      if (Newest == I) Newest = INDEX_NONE;
      continue;
    }
    ApplyEntry(I, E);
  }
}

void UUmWorldDamage::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  Step();
}

int32 UUmWorldDamage::NumShown() const {
  int32 N = 0;
  for (const FEntry& E : Entries) N += E.bShown ? 1 : 0;
  return N;
}

int32 UUmWorldDamage::FontSize() const { return FMath::RoundToInt(UUmHudTheme::Get().Font(TEXT("type.damage")).Size / UmHudTheme::PointsPerSu); }

void UUmWorldDamage::CollectParts(TArray<FS08WidgetPart>& Out) const {
  if (Newest != INDEX_NONE && Texts.IsValidIndex(Newest) && Texts[Newest]) {
    Out.Add({S08ArtHudIds::DamageText, Texts[Newest]->GetCachedWidget()});
  }
}

FText UUmWorldDamage::NewestText() const {
  return Newest != INDEX_NONE && Texts[Newest] ? Texts[Newest]->GetText() : FText::GetEmpty();
}

float UUmWorldDamage::NewestOpacity() const {
  return Newest != INDEX_NONE && Capsules[Newest] ? Capsules[Newest]->GetRenderOpacity() : 0.0f;
}

float UUmWorldDamage::NewestRiseSu() const {
  return Newest != INDEX_NONE && Capsules[Newest]
             ? static_cast<float>(-Capsules[Newest]->GetRenderTransform().Translation.Y - Entries[Newest].BaseSu)
             : 0.0f;
}

bool UUmWorldDamage::NewestHasHealIcon() const {
  return Newest != INDEX_NONE && Icons[Newest] && Icons[Newest]->GetVisibility() != ESlateVisibility::Collapsed;
}

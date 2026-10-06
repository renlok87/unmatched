// VS-2 HB-21: OPP-HAND - see UmHudOppHand.h.
#include "UmHudOppHand.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmCardMedia.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/Texture2D.h"
#include "HAL/PlatformTime.h"

const TCHAR* const UUmHudOppHand::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_OPP_HAND");

namespace UmHudOppHand {
float Step(int32 Count, float WidthSu) {
  if (Count <= 1) return StepSu;
  const float Room = FMath::Max(0.0f, WidthSu - 2.0f * PadSu - BackWSu);
  return FMath::Min(StepSu, Room / static_cast<float>(Count - 1));
}

float FanWidth(int32 Count, float WidthSu) {
  return Count <= 0 ? 0.0f : BackWSu + static_cast<float>(Count - 1) * Step(Count, WidthSu);
}

FText Caption(const FUmOppHandModel& M) {
  auto Num = [](const TCHAR* Key, const FText& N) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("n"), N);
    return UmText::Format(EUmTable::Hud, Key, Args);
  };
  const FText Deck = M.bDeckStale ? Num(TEXT("hud.opp.stale"), FText::AsNumber(M.DeckCount)) : FText::AsNumber(M.DeckCount);
  // the separator is punctuation of the caption, the words come from the table (04 §2.3)
  return FText::Format(INVTEXT("{0} · {1} · {2}"), Num(TEXT("hud.opp.hand"), FText::AsNumber(M.HandCount)),
                       Num(TEXT("hud.opp.deck"), Deck), Num(TEXT("hud.opp.discard"), FText::AsNumber(M.DiscardCount)));
}
}  // namespace UmHudOppHand

namespace {
template <typename T>
T* UmOppFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}
}  // namespace

bool UUmHudOppHand::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UBorder* PanelW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Panel")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel"))) PanelW->SetBrush(*Skin);
  PanelW->SetPadding(FMargin(UmHudOppHand::PadSu, UmHudOppHand::TopSu, UmHudOppHand::PadSu, 0.0f));
  PanelW->SetHorizontalAlignment(HAlign_Fill);
  PanelW->SetVerticalAlignment(VAlign_Fill);
  PanelW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(PanelW, nullptr)) return Fail(TEXT("Panel"));
  UVerticalBox* Column = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Column")));
  if (!Attach(Column, PanelW)) return Fail(TEXT("Column"));
  UHorizontalBox* BacksW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Backs")));
  if (!Attach(BacksW, Column)) return Fail(TEXT("Backs"));
  if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(BacksW->Slot)) {
    S->SetHorizontalAlignment(HAlign_Left);
    S->SetPadding(FMargin(0.0f));
  }
  // the row keeps the back height with no card (count 0: the caption stays where it was)
  UTextBlock* CaptionW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Caption")));
  CaptionW->SetFont(Theme.Font(TEXT("type.caption")));
  CaptionW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  if (!Attach(CaptionW, Column)) return Fail(TEXT("Caption"));
  if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(CaptionW->Slot)) {
    S->SetHorizontalAlignment(HAlign_Left);
    S->SetPadding(FMargin(0.0f, 2.0f, 0.0f, 0.0f));  // CX-09: the caption at y 75 under the backs (4 + 67)
  }
  return true;
}

UClass* UUmHudOppHand::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudOppHand::StaticClass(), WidgetBlueprintPath); }

bool UUmHudOppHand::Initialize() {
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
      }, &Error);
      if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD opp hand default tree: %s"), *Error);
    }
    Panel = UmOppFind<UBorder>(WidgetTree, TEXT("Panel"));
    Backs = UmOppFind<UHorizontalBox>(WidgetTree, TEXT("Backs"));
    Caption = UmOppFind<UTextBlock>(WidgetTree, TEXT("Caption"));
    // the theme font is the default composite font: a WBP does not keep it
    if (Caption) Caption->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
    if (Backs) {
      // the row is as high as a back with no card in it
      Backs->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  }
  return bFirst;
}

bool UUmHudOppHand::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Panel) Missing.Add(TEXT("Panel"));
  if (!Backs) Missing.Add(TEXT("Backs"));
  if (!Caption) Missing.Add(TEXT("Caption"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudOppHand::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

UWidget* UUmHudOppHand::MakeBack() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
  Box->SetWidthOverride(UmHudOppHand::BackWSu);
  Box->SetHeightOverride(UmHudOppHand::BackHSu);
  if (BackTexture) {
    const FUmCardMediaEntry* Entry = UmCardMedia::FindBack(Model.HeroSlug);
    UImage* Image = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
    FSlateBrush Brush;
    Brush.SetResourceObject(BackTexture);
    Brush.ImageSize = FVector2D(UmHudOppHand::BackWSu, UmHudOppHand::BackHSu);
    // the padded texture: the source pixels are the (0, 0) - (uv) rectangle (CP-02)
    const FVector2D Uv = Entry ? Entry->Uv : FVector2D(1.0, 1.0);
    Brush.SetUVRegion(FBox2f(FVector2f(0.0f, 0.0f), FVector2f(static_cast<float>(Uv.X), static_cast<float>(Uv.Y))));
    Image->SetBrush(Brush);
    Box->SetContent(Image);
  } else {
    // 02 §6.4: the flat back (T_Skin_Panel 48 x 67 with resource-card 24) until the hero's back is in the pak
    UBorder* Flat = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), Model.PxPerSu)) Flat->SetBrush(*Skin);
    Flat->SetHorizontalAlignment(HAlign_Center);
    Flat->SetVerticalAlignment(VAlign_Center);
    US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
    if (Icon && Icon->SetIcon(TEXT("resource-card"), 24.0f, 24)) {
      Icon->SetDisplaySizeSu(24.0f);
      Icon->ShowAtRest();
      Flat->SetContent(Icon);
    }
    Box->SetContent(Flat);
  }
  Box->SetVisibility(ESlateVisibility::HitTestInvisible);
  return Box;
}

void UUmHudOppHand::LayoutBacks() {
  if (!Backs) return;
  // the step of the target count (the leaving backs keep it while they fade)
  StepNow = UmHudOppHand::Step(Target, Model.WidthSu);
  const double T = Now();
  for (int32 I = 0; I < Pool.Num(); ++I) {
    UWidget* W = Pool[I];
    if (!W) continue;
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(W->Slot)) {
      // overlap: every back after the first starts one step after the previous (its left 20 su under the next)
      S->SetPadding(FMargin(I > 0 ? StepNow - UmHudOppHand::BackWSu : 0.0f, 0.0f, 0.0f, 0.0f));
      S->SetVerticalAlignment(VAlign_Top);
    }
    W->SetVisibility(I < Shown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  (void)T;
  Step();
}

void UUmHudOppHand::ApplyModel(const FUmOppHandModel& InModel) {
  if (bHasModel && Model == InModel) return;
  const bool bFirst = !bHasModel;
  const bool bTextureChanged = bFirst || Model.HeroSlug != InModel.HeroSlug || Model.PxPerSu != InModel.PxPerSu;
  Model = InModel;
  bHasModel = true;
  if (Panel && bTextureChanged) {
    if (const FSlateBrush* Skin = UUmHudTheme::Get().SkinFor(TEXT("panel"), Model.PxPerSu)) Panel->SetBrush(*Skin);
  }
  if (bTextureChanged && BackSlugLoaded != Model.HeroSlug) {
    BackSlugLoaded = Model.HeroSlug;
    const FUmCardMediaEntry* Entry = Model.HeroSlug.IsEmpty() ? nullptr : UmCardMedia::FindBack(Model.HeroSlug);
    BackTexture = Entry ? UmCardMedia::LoadTexture(*Entry) : nullptr;
    if (!BackTexture && !Model.HeroSlug.IsEmpty() && !bWarned) {
      bWarned = true;
      UE_LOG(LogTemp, Warning, TEXT("OPPHAND back fallback hero=%s reason=%s"), *Model.HeroSlug,
             Entry ? TEXT("texture-missing") : TEXT("no-registry-entry"));
    }
    // a new back texture: the pool is rebuilt (one texture per hero)
    if (Backs) Backs->ClearChildren();
    Pool.Reset();
    EnterStart.Reset();
    LeaveStart.Reset();
    Shown = 0;
  }
  const int32 NewTarget = FMath::Max(0, Model.HandCount);
  const double T = Now();
  while (Pool.Num() < FMath::Max(NewTarget, Shown)) {
    UWidget* Back = MakeBack();
    Pool.Add(Back);
    EnterStart.Add(-1.0);
    LeaveStart.Add(-1.0);
    if (Backs) Backs->AddChildToHorizontalBox(Back);
  }
  // grow: the new backs slide in (not on the first model: a join shows the hand at rest)
  for (int32 I = Shown; I < NewTarget; ++I) {
    EnterStart[I] = bFirst ? -1.0 : T;
    LeaveStart[I] = -1.0;
  }
  for (int32 I = 0; I < NewTarget && I < Shown; ++I) LeaveStart[I] = -1.0;  // a back that came back stops fading
  // shrink: the backs past the count fade out
  for (int32 I = NewTarget; I < Shown; ++I) {
    if (LeaveStart[I] < 0.0) LeaveStart[I] = bFirst ? T - 1.0 : T;
    EnterStart[I] = -1.0;
  }
  Target = NewTarget;
  Shown = FMath::Max(Shown, NewTarget);
  if (Caption) Caption->SetText(UmHudOppHand::Caption(Model));
  LayoutBacks();
}

bool UUmHudOppHand::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

double UUmHudOppHand::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

float UUmHudOppHand::GetBackOpacity(int32 Index) const {
  return Pool.IsValidIndex(Index) && Pool[Index] ? Pool[Index]->GetRenderOpacity() : 0.0f;
}

void UUmHudOppHand::Step() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bReduced = IsReduced();
  const double AppearMs = bReduced ? FMath::Min(100.0, Theme.Ms(TEXT("reduced.max_ms"))) : Theme.Ms(TEXT("icon.appear.ms"));
  const double LeaveMs = bReduced ? FMath::Min(100.0, Theme.Ms(TEXT("reduced.max_ms"))) : Theme.Ms(TEXT("icon.leave.ms"));
  const double T = Now();
  int32 LastShown = Target;
  for (int32 I = 0; I < Pool.Num(); ++I) {
    UWidget* W = Pool[I];
    if (!W) continue;
    float Opacity = 1.0f;
    float Dx = 0.0f;
    if (EnterStart.IsValidIndex(I) && EnterStart[I] >= 0.0) {
      const float A = FMath::Clamp(static_cast<float>((T - EnterStart[I]) * 1000.0 / FMath::Max(AppearMs, 1.0)), 0.0f, 1.0f);
      const float E = 1.0f - FMath::Pow(1.0f - A, 3.0f);  // ease out cubic
      Opacity = FMath::Lerp(bReduced ? 0.0f : 0.15f, 1.0f, bReduced ? A : E);
      Dx = bReduced ? 0.0f : -UmHudOppHand::SlideSu * (1.0f - E);
      if (A >= 1.0f) EnterStart[I] = -1.0;
    } else if (LeaveStart.IsValidIndex(I) && LeaveStart[I] >= 0.0) {
      const float A = FMath::Clamp(static_cast<float>((T - LeaveStart[I]) * 1000.0 / FMath::Max(LeaveMs, 1.0)), 0.0f, 1.0f);
      Opacity = 1.0f - A;
      if (A < 1.0f) LastShown = FMath::Max(LastShown, I + 1);
    }
    if (!FMath::IsNearlyEqual(W->GetRenderOpacity(), Opacity, 1.0e-3f)) W->SetRenderOpacity(Opacity);
    const FWidgetTransform Want(FVector2D(Dx, 0.0f), FVector2D(1.0f, 1.0f), FVector2D::ZeroVector, 0.0f);
    if (!W->GetRenderTransform().Translation.Equals(Want.Translation, 1.0e-3)) W->SetRenderTransform(Want);
  }
  // the faded backs leave the row
  if (LastShown < Shown) {
    for (int32 I = LastShown; I < Shown; ++I) {
      if (Pool.IsValidIndex(I) && Pool[I]) Pool[I]->SetVisibility(ESlateVisibility::Collapsed);
      if (LeaveStart.IsValidIndex(I)) LeaveStart[I] = -1.0;
    }
    Shown = LastShown;
  }
}

void UUmHudOppHand::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  bool bMoving = false;
  for (int32 I = 0; I < Pool.Num(); ++I) {
    bMoving |= (EnterStart.IsValidIndex(I) && EnterStart[I] >= 0.0) || (LeaveStart.IsValidIndex(I) && LeaveStart[I] >= 0.0);
  }
  if (bMoving) Step();
}

void UUmHudOppHand::SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                             const FS09OnHudPressOutcome& InOnOutcome, TFunction<void()> InOnInspect) {
  PressId = InId;
  Arbiter = InArbiter;
  OnOutcome = InOnOutcome;
  OnInspect = MoveTemp(InOnInspect);
}

FReply UUmHudOppHand::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton && OnInspect) return FReply::Handled();
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  Arbiter->Press(PressId, Arbiter->Now());
  FReply Reply = FReply::Handled();
  if (const TSharedPtr<SWidget> Cached = GetCachedWidget()) Reply.CaptureMouse(Cached.ToSharedRef());
  return Reply;
}

FReply UUmHudOppHand::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton && OnInspect) {
    // the inspector shows the hidden information only - never a face (GD-032)
    OnInspect();
    return FReply::Handled();
  }
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  const bool bOver = InGeometry.IsUnderLocation(InMouseEvent.GetScreenSpacePosition());
  const FS09HudPressOutcome Outcome = Arbiter->Release(bOver ? PressId : NAME_None, Arbiter->Now());
  if (Outcome.Result == ES09HudPressResult::Act || Outcome.Result == ES09HudPressResult::Refused) {
    OnOutcome.ExecuteIfBound(FS09HudPressArbiter::Decide(Outcome, FS09Reason()));
  }
  return FReply::Handled().ReleaseMouseCapture();
}

void UUmHudOppHand::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const {
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && bHasModel;
  const bool bPainted = bVisible && !Rect.IsEmpty();
  const FString State = FString::Printf(TEXT("count=%d"), Model.HandCount);
  const FString Extra = FString::Printf(TEXT("deck=%d discard=%d stale=%d step=%.1f width=%.0f fan=%.1f back=%s"),
                                        Model.DeckCount, Model.DiscardCount, Model.bDeckStale ? 1 : 0, StepNow,
                                        Model.WidthSu, UmHudOppHand::FanWidth(Model.HandCount, Model.WidthSu),
                                        BackTexture ? *BackTexture->GetName() : TEXT("fallback"));
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-OPP-HAND"), TEXT("umg"), *State, FString(), Rect, bPainted, bVisible,
                                        SourceName(), Extra));
}

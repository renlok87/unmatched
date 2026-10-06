// VS-2 HB-14: the connection chip of TOP - see UmConnectionBadge.h.
#include "UmConnectionBadge.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "../S08TraceLog.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "HAL/PlatformTime.h"
#include "Misc/PackageName.h"

const TCHAR* const UUmConnectionBadge::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmConnectionBadge");

namespace UmConnection {
EUmConnState Resolve(const FUmConnInput& In) {
  if (!In.bStreamReady) return In.bWasReady ? EUmConnState::Lost : EUmConnState::Syncing;
  if (In.bCommandSlow || In.bRecovering) return EUmConnState::Syncing;
  return EUmConnState::Online;
}

const TCHAR* StateName(EUmConnState State) {
  switch (State) {
    case EUmConnState::Syncing: return TEXT("syncing");
    case EUmConnState::Lost: return TEXT("lost");
    default: return TEXT("online");
  }
}

FName IconId(EUmConnState State) {
  switch (State) {
    case EUmConnState::Syncing: return FName(TEXT("resource-connection-reconnecting"));
    case EUmConnState::Lost: return FName(TEXT("resource-connection-lost"));
    default: return FName(TEXT("resource-connection-online"));
  }
}

const TCHAR* TooltipKey(EUmConnState State) {
  switch (State) {
    case EUmConnState::Syncing: return TEXT("hud.conn.syncing");
    case EUmConnState::Lost: return TEXT("hud.conn.lost");
    default: return TEXT("hud.conn.online");
  }
}

FName AppearAnim(EUmConnState From, EUmConnState To) {
  // the contract's own transition: the online bars slide out under the stamped X
  if (From == EUmConnState::Online && To == EUmConnState::Lost) return FName(TEXT("appear_from_online"));
  return FName(TEXT("appear"));
}
}  // namespace UmConnection

namespace {
template <typename T>
T* UmConnMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

template <typename T>
T* UmConnFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}
}  // namespace

UClass* UUmConnectionBadge::WidgetClass() {
  const FString Package = WidgetBlueprintPath;
  if (FPackageName::DoesPackageExist(Package)) {
    const FString ClassPath = Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C");
    if (UClass* Wbp = LoadClass<UUmConnectionBadge>(nullptr, *ClassPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) return Wbp;
  }
  return UUmConnectionBadge::StaticClass();
}

bool UUmConnectionBadge::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* SizeBox = UmConnMake<USizeBox>(Tree, TEXT("Box"));
  SizeBox->SetWidthOverride(UmConnection::ZoneLSu);
  SizeBox->SetHeightOverride(UmConnection::ZoneLSu);
  if (!Attach(SizeBox, nullptr)) return Fail(TEXT("Box"));
  UOverlay* Stack = UmConnMake<UOverlay>(Tree, TEXT("Stack"));
  Stack->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Stack, SizeBox)) return Fail(TEXT("Stack"));
  US08AnimatedIconWidget* IconWidget = UmConnMake<US08AnimatedIconWidget>(Tree, TEXT("Icon"));
  if (!Attach(IconWidget, Stack)) return Fail(TEXT("Icon"));
  if (UOverlaySlot* IconSlot = Cast<UOverlaySlot>(IconWidget->Slot)) {
    IconSlot->SetHorizontalAlignment(HAlign_Center);
    IconSlot->SetVerticalAlignment(VAlign_Center);
  }
  UTextBlock* Fallback = UmConnMake<UTextBlock>(Tree, TEXT("FallbackText"));
  Fallback->SetFont(Theme.Font(TEXT("type.tag")));
  Fallback->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  Fallback->SetShadowOffset(FVector2D::ZeroVector);
  Fallback->SetJustification(ETextJustify::Center);
  Fallback->SetAutoWrapText(true);
  Fallback->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Fallback, Stack)) return Fail(TEXT("FallbackText"));
  if (UOverlaySlot* TextSlot = Cast<UOverlaySlot>(Fallback->Slot)) {
    TextSlot->SetHorizontalAlignment(HAlign_Center);
    TextSlot->SetVerticalAlignment(VAlign_Center);
  }
  return true;
}

bool UUmConnectionBadge::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD conn default tree: %s"), *Error);
    Box = UmConnFind<USizeBox>(Tree, TEXT("Box"));
    Icon = UmConnFind<US08AnimatedIconWidget>(Tree, TEXT("Icon"));
    FallbackText = UmConnFind<UTextBlock>(Tree, TEXT("FallbackText"));
  }
  // the chip takes the hover (its tooltip) and nothing else: a click on it does nothing
  if (bFirst) {
    // the theme font is the default composite font (FSlateFontInfo without a font object): a WBP does not keep it
    // (the text would draw as tofu) - every load takes it from the theme again
    if (FallbackText) FallbackText->SetFont(UUmHudTheme::Get().Font(TEXT("type.tag")));
    SetVisibility(ESlateVisibility::Visible);
  }
  return bFirst;
}

bool UUmConnectionBadge::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Box) Missing.Add(TEXT("Box"));
  if (!Icon) Missing.Add(TEXT("Icon"));
  if (!FallbackText) Missing.Add(TEXT("FallbackText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

double UUmConnectionBadge::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

void UUmConnectionBadge::ApplyState(EUmConnState InState, float ZoneSu) {
  if (Box && ZoneShown != ZoneSu) {
    Box->SetWidthOverride(ZoneSu);
    Box->SetHeightOverride(ZoneSu);
    ZoneShown = ZoneSu;
  }
  if (bHasState && InState == State) return;
  const EUmConnState From = State;
  const bool bFirst = !bHasState;
  State = InState;
  bHasState = true;
  const FName Id = UmConnection::IconId(State);
  bool bIcon = false;
  if (Icon) {
    bool bClamped = false;
    const int32 Px = S08IconMotion::ExportSizePx(UmConnection::IconSu, UmHudScale::Current().PxPerSu(), &bClamped);
    bIcon = Icon->SetIcon(Id, UmConnection::IconSu, Px);
    if (bIcon) {
      Icon->SetDisplaySizeSu(UmConnection::IconSu);
      bIcon = Icon->GetLayerTexture(0, 0) != nullptr;
    }
  }
  if (bIcon) {
    // reduced motion: the contract's reduced branch (100 ms fade, no cycle)
    Icon->SetReducedMotion(S08IconMotion::IsReducedMotion());
    if (bFirst) {
      Icon->ShowAtRest();
      LastAnim = FName(TEXT("rest"));
    } else {
      LastAnim = UmConnection::AppearAnim(From, State);
      if (!Icon->PlayAnim(LastAnim)) {
        LastAnim = FName(TEXT("appear"));
        Icon->PlayAnim(LastAnim);
      }
    }
    Icon->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (FallbackText) FallbackText->SetVisibility(ESlateVisibility::Collapsed);
    ShownIcon = Id;
  } else {
    // ВР-HB08: the text instead of a missing glyph, one trace per badge
    if (Icon) Icon->SetVisibility(ESlateVisibility::Collapsed);
    if (FallbackText) {
      FallbackText->SetText(UmText::Get(EUmTable::Hud, UmConnection::TooltipKey(State)));
      FallbackText->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
    ShownIcon = NAME_None;
    LastAnim = FName(TEXT("fallback"));
    if (!bMissingTraced) {
      bMissingTraced = true;
      FS08Trace::Write(FString::Printf(TEXT("ICON missing=%s block=UI-HUD-CONN"), *Id.ToString()));
    }
  }
  if (bTooltipShown) SetToolTipText(GetTooltipText());
}

FText UUmConnectionBadge::GetTooltipText() const { return UmText::Get(EUmTable::Hud, UmConnection::TooltipKey(State)); }

void UUmConnectionBadge::StepTooltip() {
  if (bHovered && !bTooltipShown && HoverSince >= 0.0 && Now() - HoverSince >= UmConnection::TooltipDelaySeconds) {
    bTooltipShown = true;
    SetToolTipText(GetTooltipText());
  }
}

void UUmConnectionBadge::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (bHovered && !bTooltipShown) StepTooltip();
}

void UUmConnectionBadge::SimulateHover(bool bIn) {
  if (bHovered == bIn) return;
  bHovered = bIn;
  HoverSince = bIn ? Now() : -1.0;
  if (!bIn && bTooltipShown) {
    bTooltipShown = false;
    SetToolTipText(FText::GetEmpty());
  }
}

void UUmConnectionBadge::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  SimulateHover(true);
}

void UUmConnectionBadge::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  SimulateHover(false);
}

FString UUmConnectionBadge::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

FString UUmConnectionBadge::ShotLine(const FS08ScreenRect& Rect, const FString& Source) const {
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && bHasState;
  const bool bPainted = bVisible && !Rect.IsEmpty();
  const FString Extra = FString::Printf(TEXT("icon=%s anim=%s"),
                                        ShownIcon.IsNone() ? TEXT("fallback") : *ShownIcon.ToString(), *LastAnim.ToString());
  return S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-CONN"), TEXT("umg"), UmConnection::StateName(State), FString(), Rect,
                                       bPainted, bVisible, Source, Extra);
}

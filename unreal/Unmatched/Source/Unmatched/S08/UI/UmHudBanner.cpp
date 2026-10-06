// VS-2 HB-16: the "ВАШ ХОД" banner - see UmHudBanner.h.
#include "UmHudBanner.h"

#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/TextBlock.h"

const TCHAR* const UUmHudBanner::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_BANNER");

UClass* UUmHudBanner::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudBanner::StaticClass(), WidgetBlueprintPath); }

bool UUmHudBanner::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UBorder* PlateWidget = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Plate")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel"))) PlateWidget->SetBrush(*Skin);
  PlateWidget->SetPadding(FMargin(0.0f));
  PlateWidget->SetHorizontalAlignment(HAlign_Center);
  PlateWidget->SetVerticalAlignment(VAlign_Center);
  PlateWidget->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(PlateWidget, nullptr)) return Fail(TEXT("Plate"));
  UTextBlock* TextWidget = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Text")));
  TextWidget->SetFont(Theme.Font(TEXT("type.banner")));
  TextWidget->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("turn.flash.yellow"))));
  TextWidget->SetShadowOffset(FVector2D::ZeroVector);
  TextWidget->SetJustification(ETextJustify::Center);
  TextWidget->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.banner.own_turn")));
  if (!Attach(TextWidget, PlateWidget)) return Fail(TEXT("Text"));
  return true;
}

bool UUmHudBanner::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD banner default tree: %s"), *Error);
    Plate = Cast<UBorder>(Tree->FindWidget(FName(TEXT("Plate"))));
    Text = Cast<UTextBlock>(Tree->FindWidget(FName(TEXT("Text"))));
  }
  if (bFirst) {
    // the string table text of the current UI language (the WBP may carry the one of its authoring)
    if (Text) Text->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.banner.own_turn")));
    // the theme font is the default composite font (FSlateFontInfo without a font object): a WBP does not keep it
    // (the text would draw as tofu) - every load takes it from the theme again
    if (Text) Text->SetFont(UUmHudTheme::Get().Font(TEXT("type.banner")));
    SetRenderOpacity(0.0f);
    SetVisibility(ESlateVisibility::Collapsed);
  }
  return bFirst;
}

bool UUmHudBanner::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Plate) Missing.Add(TEXT("Plate"));
  if (!Text) Missing.Add(TEXT("Text"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmHudBanner::SetPxPerSu(float InPxPerSu) {
  if (PxPerSu == InPxPerSu) return;
  PxPerSu = InPxPerSu;
  if (Plate) {
    if (const FSlateBrush* Skin = UUmHudTheme::Get().SkinFor(TEXT("panel"), PxPerSu)) Plate->SetBrush(*Skin);
  }
}

void UUmHudBanner::ApplyModel(const FS09TurnCue& Cue, double NowMs, bool bShow) {
  const float NewAlpha = bShow ? Cue.BannerAlpha(NowMs) : 0.0f;
  if (NewAlpha == Alpha) return;
  const bool bWasShown = Alpha > 0.0f;
  Alpha = NewAlpha;
  SetRenderOpacity(Alpha);
  // never a hit-test target; collapsed (no paint) outside the 600 ms
  if (bWasShown != (Alpha > 0.0f)) {
    if (Alpha > 0.0f && Text) Text->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.banner.own_turn")));
    SetVisibility(Alpha > 0.0f ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
}

FString UUmHudBanner::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudBanner::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const {
  if (Alpha <= 0.0f) return;
  const bool bPainted = !Rect.IsEmpty();
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-BANNER"), TEXT("umg"), TEXT("shown"), FString(), Rect, bPainted, true,
                                        SourceName(), FString::Printf(TEXT("alpha=%.2f"), Alpha)));
}

// VS-4 HB-41: the subtitle capsule - see UmHudSubtitle.h.
#include "UmHudSubtitle.h"

#include "UmGameHud.h"
#include "UmHudFeed.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/TextBlock.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"

const TCHAR* const UUmHudSubtitle::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_SUB");

namespace UmHudSubtitle {
float MeasureSu(const FString& Text, float SizeSu, FName Token, float PxPerSu) {
  if (Text.IsEmpty()) return 0.0f;
  if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().GetRenderer()) return 0.5f * SizeSu * Text.Len();
  FSlateFontInfo Font = UUmHudTheme::Get().Font(Token);
  Font.Size = UmHudTheme::PointsFromSu(SizeSu);
  const float Scale = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  const TSharedRef<FSlateFontMeasure> M = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  return static_cast<float>(M->Measure(Text, Font, Scale).X) / Scale;
}

FText SpeakerText(const FString& Name) {
  if (Name.IsEmpty()) return FText::GetEmpty();
  FFormatNamedArguments Args;
  Args.Add(TEXT("name"), FText::FromString(Name));
  return UmText::Format(EUmTable::Hud, TEXT("hud.sub.speaker"), Args);
}

FUmSubtitlePlan Plan(const FUmSubtitleModel& Model, FMeasure Measure) {
  using namespace UmHudFeed;
  constexpr float Slack = 6.0f;  // ВР-VS4-20
  FUmSubtitlePlan P;
  const FString S = Model.Speaker.ToString();
  const FString L = Model.Line.ToString();
  P.SpeakerWidthSu = S.IsEmpty() ? 0.0f : FMath::CeilToFloat(Measure(S, 14.0f, FName(TEXT("type.tag")))) + Slack;
  const float Lead = P.SpeakerWidthSu > 0.0f ? P.SpeakerWidthSu + SpeakerGapSu : 0.0f;
  const float Room = SubMaxWSu - 2.0f * SubPadXSu - Lead;
  const float W = FMath::CeilToFloat(Measure(L, 16.0f, FName(TEXT("type.body")))) + Slack;
  if (W <= Room) {
    P.LineWidthSu = W;
    P.Lines = 1;
  } else {
    float Widest = 0.0f;
    P.Lines = FMath::Max(2, UmHudStatus::WrapLines(L, FMath::Max(1.0f, Room - Slack), 16.0f,
                                                    [&Measure](const FString& T, float Su) { return Measure(T, Su, FName(TEXT("type.body"))); },
                                                    &Widest));
    P.LineWidthSu = FMath::Min(Room, FMath::CeilToFloat(Widest) + Slack);
  }
  const float H = FMath::Max(SubMinHSu, LineBoxSu * static_cast<float>(P.Lines) + 2.0f * SubPadYSu);
  P.SizeSu = FVector2D(FMath::CeilToFloat(2.0f * SubPadXSu + Lead + P.LineWidthSu), FMath::CeilToFloat(H));
  return P;
}
}  // namespace UmHudSubtitle

UClass* UUmHudSubtitle::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudSubtitle::StaticClass(), WidgetBlueprintPath); }

bool UUmHudSubtitle::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  UBorder* CapsuleW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Capsule")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("capsule"))) CapsuleW->SetBrush(*Skin);
  CapsuleW->SetPadding(FMargin(UmHudFeed::SubPadXSu, UmHudFeed::SubPadYSu));
  CapsuleW->SetHorizontalAlignment(HAlign_Left);
  CapsuleW->SetVerticalAlignment(VAlign_Center);
  CapsuleW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(CapsuleW, RootW)) return Fail(TEXT("Capsule"));
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(CapsuleW->Slot)) {
    S->SetAutoSize(false);
    S->SetAnchors(FAnchors(0.0f, 0.0f));
  }
  UHorizontalBox* RowW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Row")));
  RowW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(RowW, CapsuleW)) return Fail(TEXT("Row"));
  auto Text = [&Tree, &Theme](const TCHAR* Name, const TCHAR* Type, const TCHAR* Color) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetFont(Theme.Font(Type));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
    T->SetShadowOffset(FVector2D::ZeroVector);
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    return T;
  };
  UTextBlock* SpeakerW = Text(TEXT("Speaker"), TEXT("type.tag"), TEXT("card.cream"));
  if (!Attach(SpeakerW, RowW)) return Fail(TEXT("Speaker"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(SpeakerW->Slot)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetPadding(FMargin(0.0f, 0.0f, UmHudFeed::SpeakerGapSu, 0.0f));
  }
  UTextBlock* LineW = Text(TEXT("Line"), TEXT("type.body"), TEXT("text.primary"));
  if (!Attach(LineW, RowW)) return Fail(TEXT("Line"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(LineW->Slot)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
  }
  return true;
}

bool UUmHudSubtitle::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD subtitle default tree: %s"), *Error);
  }
  if (bFirst) {
    BindFromTree();
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    // the theme fonts are the default composite font: a WBP does not keep them
    if (Speaker) Speaker->SetFont(Theme.Font(TEXT("type.tag")));
    if (Line) Line->SetFont(Theme.Font(TEXT("type.body")));
    SetVisibility(ESlateVisibility::Collapsed);
  }
  return bFirst;
}

void UUmHudSubtitle::BindFromTree() {
  UWidgetTree* Tree = WidgetTree;
  if (!Tree) return;
  Root = Cast<UCanvasPanel>(Tree->FindWidget(FName(TEXT("Root"))));
  Capsule = Cast<UBorder>(Tree->FindWidget(FName(TEXT("Capsule"))));
  Row = Cast<UHorizontalBox>(Tree->FindWidget(FName(TEXT("Row"))));
  Speaker = Cast<UTextBlock>(Tree->FindWidget(FName(TEXT("Speaker"))));
  Line = Cast<UTextBlock>(Tree->FindWidget(FName(TEXT("Line"))));
}

bool UUmHudSubtitle::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Capsule) Missing.Add(TEXT("Capsule"));
  if (!Speaker) Missing.Add(TEXT("Speaker"));
  if (!Line) Missing.Add(TEXT("Line"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudSubtitle::SourceName() const { return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName(); }

void UUmHudSubtitle::SetPxPerSu(float InPxPerSu, bool bInReduced) {
  bReduced = bInReduced;
  if (PxPerSu == InPxPerSu) return;
  PxPerSu = InPxPerSu;
  if (Capsule) {
    if (const FSlateBrush* Skin = UUmHudTheme::Get().SkinFor(TEXT("capsule"), PxPerSu)) Capsule->SetBrush(*Skin);
  }
  if (bShown) Restyle();
}

void UUmHudSubtitle::Restyle() {
  const float Px = PxPerSu;
  PlanNow = UmHudSubtitle::Plan(Model, [this, Px](const FString& T, float S, FName Tok) {
    return MeasureOverride ? MeasureOverride(T, S, Tok) : UmHudSubtitle::MeasureSu(T, S, Tok, Px);
  });
  if (Speaker) {
    Speaker->SetText(Model.Speaker);
    Speaker->SetVisibility(Model.Speaker.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  if (Line) {
    Line->SetText(Model.Line);
    Line->SetAutoWrapText(false);
    Line->SetWrapTextAt(PlanNow.Lines > 1 ? PlanNow.LineWidthSu : 0.0f);
  }
  if (Capsule) {
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Capsule->Slot)) S->SetSize(PlanNow.SizeSu);
  }
}

void UUmHudSubtitle::ApplyModel(const FUmSubtitleModel& InModel) {
  if (!InModel.IsSet()) {
    Hide();
    return;
  }
  Model = InModel;
  bShown = true;
  bPlaced = false;
  Restyle();
  SetRenderOpacity(bReduced ? 1.0f : 0.0f);
  SetVisibility(ESlateVisibility::Collapsed);  // drawn once placed
}

void UUmHudSubtitle::Hide() {
  bShown = false;
  bPlaced = false;
  RectSu = FBox2D(ForceInit);
  SetVisibility(ESlateVisibility::Collapsed);
}

bool UUmHudSubtitle::IsShown() const { return bShown; }

bool UUmHudSubtitle::Tick(double NowMs) {
  if (!bShown) return false;
  if (NowMs >= Model.StartMs + Model.DurationMs) {
    Hide();
    return true;
  }
  const float In = bReduced ? 0.0f : UUmHudTheme::Get().Ms(TEXT("hover.ms"));  // <= 150
  const float A = In <= 0.0f ? 1.0f : FMath::Clamp(static_cast<float>((NowMs - Model.StartMs) / In), 0.0f, 1.0f);
  if (!FMath::IsNearlyEqual(GetRenderOpacity(), A, 1.0e-3f)) SetRenderOpacity(A);
  return false;
}

void UUmHudSubtitle::ApplyPlacement(const FBox2D& InRectSu, bool bInLowered) {
  bLowered = bInLowered;
  if (!bShown || !InRectSu.bIsValid) {
    bPlaced = false;
    SetVisibility(ESlateVisibility::Collapsed);
    return;
  }
  RectSu = InRectSu;
  bPlaced = true;
  if (Capsule) {
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Capsule->Slot)) {
      S->SetPosition(InRectSu.Min);
      S->SetSize(InRectSu.GetSize());
    }
  }
  SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UUmHudSubtitle::CollectShotLines(TArray<FString>& Out) const {
  if (!bShown || !bPlaced || !RectSu.bIsValid) return;
  const float Px = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  Rect.X0 = static_cast<float>(RectSu.Min.X) * Px;
  Rect.Y0 = static_cast<float>(RectSu.Min.Y) * Px;
  Rect.X1 = static_cast<float>(RectSu.Max.X) * Px;
  Rect.Y1 = static_cast<float>(RectSu.Max.Y) * Px;
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-SUB"), TEXT("umg"), TEXT("shown"), FString(), Rect, true, true, SourceName(),
                                        FString::Printf(TEXT("lines=%d speaker=%d lowered=%d"), PlanNow.Lines,
                                                        Model.Speaker.IsEmpty() ? 0 : 1, bLowered ? 1 : 0)));
}

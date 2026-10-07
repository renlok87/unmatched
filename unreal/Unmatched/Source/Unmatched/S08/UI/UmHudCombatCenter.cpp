// VS-3 HB-33: the combat centre - see UmHudCombatCenter.h.
#include "UmHudCombatCenter.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08IconMotion.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "HAL/PlatformTime.h"

const TCHAR* const UUmHudCombatCenter::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_COMBAT");

FString FUmCenterLine::Display() const {
  if (Text.IsEmpty()) return Title;
  if (Title.IsEmpty()) return Text;
  return Title + TEXT(": ") + Text;
}

namespace UmHudCombatCenter {
const TCHAR* StateName(EUmCenterState State) {
  switch (State) {
    case EUmCenterState::Wait: return TEXT("wait");
    case EUmCenterState::Read: return TEXT("read");
    case EUmCenterState::Effects: return TEXT("effects");
    case EUmCenterState::Slam: return TEXT("slam");
    case EUmCenterState::Hit: return TEXT("hit");
    default: return TEXT("");
  }
}

float LineBoxSu(int32 Rows) { return 2.0f + RowPitchSu * FMath::Max(1, Rows); }

FString FitLine(const FString& Display, float ColumnSu, int32& OutRows, bool& bOutEllipsis) {
  const TArray<float> Sizes = {BodySu};
  const FUmStatusFit Fit = UmHudStatus::Fit(Display, ColumnSu, Sizes, [](const FString& T, float S) {
    return UmDeckRow::MeasureSu(T, S, FName(TEXT("type.body")));
  });
  OutRows = FMath::Clamp(Fit.Lines, 1, MaxRows);
  bOutEllipsis = Fit.bEllipsis;
  return Fit.Display;
}

FPlan Plan(EUmCenterState State, bool bScore, const TArray<int32>& Rows, int32 Current, bool bClassS) {
  FPlan P;
  if (State == EUmCenterState::Hidden || State == EUmCenterState::Read) return P;
  if (State == EUmCenterState::Wait) {
    P.HeightSu = 2.0f * PadSu + WaitHSu;
    return P;
  }
  const int32 N = Rows.Num();
  const int32 Max = bClassS ? MaxLinesS : MaxLinesL;
  const bool bWithScore = bScore && (State == EUmCenterState::Slam || State == EUmCenterState::Hit);
  const float Base = 2.0f * PadSu + (bWithScore ? ScoreInkSu + ScoreGapSu + OutcomeInkSu : 0.0f);
  // effects: the window ends at the current line (the first lines while nothing is lit); slam / hit: from the first
  const int32 End = (!bWithScore && Current >= 0) ? FMath::Min(Current, N - 1) : FMath::Min(Max, N) - 1;
  const int32 First = bWithScore ? 0 : FMath::Max(0, End - Max + 1);
  const int32 Avail = FMath::Min(Max, N - First);
  for (int32 C = Avail; C >= 0; --C) {
    float H = Base;
    for (int32 I = 0; I < C; ++I) H += (I > 0 ? LineGapSu : 0.0f) + LineBoxSu(Rows[First + I]);
    if (C > 0 && bWithScore) H += OutcomeGapSu;
    const int32 More = N - C;
    if (More > 0) H += (C > 0 ? LineGapSu : (bWithScore ? OutcomeGapSu : 0.0f)) + ChipHSu;
    if (H <= MaxHeightSu + 0.01f || C == 0) {
      P.First = C > 0 ? First : 0;
      P.Count = C;
      P.More = More;
      P.HeightSu = FMath::Min(H, MaxHeightSu);
      return P;
    }
  }
  return P;
}
}  // namespace UmHudCombatCenter

namespace {
template <typename T>
T* UmCenterFind(UWidgetTree* Tree, const FString& Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(*Name))) : nullptr;
}

void UmCenterPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, int32 Z, bool bAuto = false) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(bAuto);
    S->SetPosition(Pos);
    if (!bAuto) S->SetSize(Size);
    S->SetZOrder(Z);
  }
}

void UmCenterShow(UWidget* W, bool bOn) {
  if (!W) return;
  const ESlateVisibility Want = bOn ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed;
  if (W->GetVisibility() != Want) W->SetVisibility(Want);
}

void UmCenterText(UTextBlock* T, FName Type, FName Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(Type));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

/** The distance from the text block's top to the cap top of its first row (su): ascent - cap height (Roboto 0.711 em). */
float UmCenterCapInsetSu(float SizeSu, FName Token) { return FMath::Max(0.0f, UmDeckRow::AscentSu(SizeSu, Token) - 0.711f * SizeSu); }
}  // namespace

UClass* UUmHudCombatCenter::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmHudCombatCenter::StaticClass(), WidgetBlueprintPath);
}

bool UUmHudCombatCenter::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const FString& What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), *What);
    return false;
  };
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  UBorder* PanelW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Panel")));
  PanelW->SetVisibility(ESlateVisibility::HitTestInvisible);
  PanelW->SetPadding(FMargin(0.0f));
  if (!Attach(PanelW, RootW)) return Fail(TEXT("Panel"));
  for (const TCHAR* Name : {TEXT("WaitText"), TEXT("ScoreText"), TEXT("OutcomeText")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::Collapsed);
    T->SetJustification(ETextJustify::Center);
    if (!Attach(T, RootW)) return Fail(Name);
  }
  UVerticalBox* Lines = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("EffectLines")));
  Lines->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(Lines, RootW)) return Fail(TEXT("EffectLines"));
  for (int32 I = 0; I < PoolSize; ++I) {
    USizeBox* Box = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(*FString::Printf(TEXT("Line%d"), I)));
    Box->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(Box, Lines)) return Fail(TEXT("Line"));
    UCanvasPanel* Row = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(*FString::Printf(TEXT("Row%d"), I)));
    if (!Attach(Row, Box)) return Fail(TEXT("Row"));
    UImage* Bar = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(*FString::Printf(TEXT("Bar%d"), I)));
    Bar->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(Bar, Row)) return Fail(TEXT("Bar"));
    US08AnimatedIconWidget* Mark =
        Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(*FString::Printf(TEXT("Mark%d"), I)));
    Mark->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(Mark, Row)) return Fail(TEXT("Mark"));
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*FString::Printf(TEXT("Text%d"), I)));
    if (!Attach(T, Row)) return Fail(TEXT("Text"));
  }
  UBorder* Chip = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("MoreChip")));
  Chip->SetVisibility(ESlateVisibility::Collapsed);
  Chip->SetPadding(FMargin(UmHudCombatCenter::ChipPadSu, 0.0f));
  Chip->SetVerticalAlignment(VAlign_Center);
  if (!Attach(Chip, RootW)) return Fail(TEXT("MoreChip"));
  UTextBlock* More = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("MoreText")));
  if (!Attach(More, Chip)) return Fail(TEXT("MoreText"));
  return true;
}

bool UUmHudCombatCenter::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD combat centre default tree: %s"), *Error);
  }
  Root = UmCenterFind<UCanvasPanel>(WidgetTree, TEXT("Root"));
  Panel = UmCenterFind<UBorder>(WidgetTree, TEXT("Panel"));
  WaitText = UmCenterFind<UTextBlock>(WidgetTree, TEXT("WaitText"));
  ScoreText = UmCenterFind<UTextBlock>(WidgetTree, TEXT("ScoreText"));
  OutcomeText = UmCenterFind<UTextBlock>(WidgetTree, TEXT("OutcomeText"));
  EffectLines = UmCenterFind<UVerticalBox>(WidgetTree, TEXT("EffectLines"));
  MoreChip = UmCenterFind<UBorder>(WidgetTree, TEXT("MoreChip"));
  MoreText = UmCenterFind<UTextBlock>(WidgetTree, TEXT("MoreText"));
  LineBoxes.Reset();
  LineBars.Reset();
  LineMarks.Reset();
  LineTexts.Reset();
  for (int32 I = 0; I < PoolSize; ++I) {
    LineBoxes.Add(UmCenterFind<USizeBox>(WidgetTree, FString::Printf(TEXT("Line%d"), I)));
    LineBars.Add(UmCenterFind<UImage>(WidgetTree, FString::Printf(TEXT("Bar%d"), I)));
    LineMarks.Add(UmCenterFind<US08AnimatedIconWidget>(WidgetTree, FString::Printf(TEXT("Mark%d"), I)));
    LineTexts.Add(UmCenterFind<UTextBlock>(WidgetTree, FString::Printf(TEXT("Text%d"), I)));
  }
  StampPlayed.Init(FString(), PoolSize);
  // a WBP keeps neither the theme fonts nor the colours of the code tree: set at run time
  UmCenterText(WaitText, TEXT("type.heading"), TEXT("text.primary"));
  UmCenterText(ScoreText, TEXT("type.display"), TEXT("text.primary"));
  UmCenterText(OutcomeText, TEXT("type.title"), TEXT("text.primary"));
  UmCenterText(MoreText, TEXT("type.tag"), TEXT("text.primary"));
  for (UTextBlock* T : LineTexts) UmCenterText(T, TEXT("type.body"), TEXT("text.secondary"));
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (MoreChip) MoreChip->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg.inset")), Theme.RadiusSu(TEXT("radius.s"))));
  for (UImage* Bar : LineBars) {
    if (Bar) Bar->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("state.pending")), 0.0f));
  }
  if (Root) Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

bool UUmHudCombatCenter::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Root) Missing.Add(TEXT("Root"));
  if (!Panel) Missing.Add(TEXT("Panel"));
  if (!ScoreText) Missing.Add(TEXT("ScoreText"));
  if (!OutcomeText) Missing.Add(TEXT("OutcomeText"));
  if (!EffectLines) Missing.Add(TEXT("EffectLines"));
  if (!MoreText) Missing.Add(TEXT("MoreText"));
  for (int32 I = 0; I < PoolSize; ++I) {
    if (!LineBoxes.IsValidIndex(I) || !LineBoxes[I] || !LineTexts[I] || !LineMarks[I] || !LineBars[I]) {
      Missing.Add(FString::Printf(TEXT("Line%d"), I));
    }
  }
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudCombatCenter::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudCombatCenter::SetClockOverrideMs(double Ms) {
  ClockOverrideMs = Ms;
  for (US08AnimatedIconWidget* Mark : LineMarks) {
    if (Mark) Mark->SetClockOverrideMs(Ms >= 0.0 ? static_cast<float>(Ms) : -1.0f);
  }
}

double UUmHudCombatCenter::NowMs() const { return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0; }

bool UUmHudCombatCenter::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride != 0 : S08IconMotion::IsReducedMotion();
}

void UUmHudCombatCenter::SetFrame(const FUmCombatCenterFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  Frame = InFrame;
  bHasFrame = true;
  if (bHasModel) Relayout();
}

FBox2D UUmHudCombatCenter::PanelRectSu() const {
  using namespace UmHudCombatCenter;
  if (!bHasModel || PlanNow.HeightSu <= 0.0f) return FBox2D(ForceInit);
  const float W = Frame.bClassS ? WidthSSu : WidthLSu;
  float Top = Frame.bClassS ? TopSSu : TopLSu;
  if (Frame.StatusBottomSu > 0.0f) Top = FMath::Max(Top, Frame.StatusBottomSu + 8.0f);
  const float X = 0.5f * (static_cast<float>(Frame.CanvasSu.X) - W);
  return FBox2D(FVector2D(X, Top), FVector2D(X + W, Top + PlanNow.HeightSu));
}

void UUmHudCombatCenter::ApplyModel(const FUmCombatCenterModel& InModel) {
  if (bHasModel && Model == InModel) return;
  const EUmCenterState Was = bHasModel ? Model.State : EUmCenterState::Hidden;
  Model = InModel;
  bHasModel = true;
  const bool bSlamNow = Model.State == EUmCenterState::Slam || Model.State == EUmCenterState::Hit;
  const bool bSlamWas = Was == EUmCenterState::Slam || Was == EUmCenterState::Hit;
  if (bSlamNow && !bSlamWas && Model.bScore) SlamStartMs = NowMs();
  if (!bSlamNow) SlamStartMs = -1.0;
  Relayout();
}

void UUmHudCombatCenter::Relayout() {
  using namespace UmHudCombatCenter;
  const bool bShow = Model.State != EUmCenterState::Hidden && Model.State != EUmCenterState::Read;
  // fit every line to the text column (the plan needs the rows of each)
  const float W = Frame.bClassS ? WidthSSu : WidthLSu;
  const float Column = W - TextLeftSu - PadSu;
  TArray<int32> Rows;
  TArray<FString> Fitted;
  TArray<bool> Ellipsis;
  for (const FUmCenterLine& L : Model.Lines) {
    int32 R = 1;
    bool bE = false;
    Fitted.Add(FitLine(L.Display(), Column, R, bE));
    Rows.Add(R);
    Ellipsis.Add(bE);
  }
  PlanNow = Plan(Model.State, Model.bScore, Rows, Model.Current, Frame.bClassS);
  ShownTexts.Reset();
  EllipsisCount = 0;
  if (!bShow) {
    SetVisibility(ESlateVisibility::Collapsed);
    return;
  }
  SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const FBox2D PanelSu = PanelRectSu();
  const FVector2D P = FVector2D(PanelSu.Min) - Frame.OriginSu;
  if (Panel) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), Frame.PxPerSu)) Panel->SetBrush(*Skin);
    UmCenterPlace(Panel, P, FVector2D(W, PlanNow.HeightSu), 0);
  }
  // wait
  const bool bWait = Model.State == EUmCenterState::Wait;
  UmCenterShow(WaitText, bWait);
  if (bWait && WaitText) {
    WaitText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.combat.wait.defense")));
    UmCenterPlace(WaitText, P + FVector2D(PadXSu, PadSu + 0.5f * (WaitHSu - 24.0f * 1.17f)), FVector2D(W - 2.0f * PadXSu, WaitHSu), 1);
  }
  // score and outcome
  const bool bWithScore = Model.bScore && (Model.State == EUmCenterState::Slam || Model.State == EUmCenterState::Hit);
  UmCenterShow(ScoreText, bWithScore);
  UmCenterShow(OutcomeText, bWithScore);
  float Y = PadSu;
  if (bWithScore) {
    if (ScoreText) {
      FFormatNamedArguments A;
      A.Add(TEXT("a"), FText::FromString(Model.AttackValue >= 0 ? FString::FromInt(Model.AttackValue) : FString(TEXT("?"))));
      A.Add(TEXT("d"), FText::FromString(Model.DefenseValue >= 0 ? FString::FromInt(Model.DefenseValue) : FString(TEXT("?"))));
      ScoreText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.combat.score"), A));
      const float Inset = UmCenterCapInsetSu(48.0f, TEXT("type.display"));
      UmCenterPlace(ScoreText, P + FVector2D(PadXSu, Y - Inset), FVector2D(W - 2.0f * PadXSu, ScoreInkSu + Inset + 14.0f), 1);
      ScoreText->SetRenderTransformPivot(FVector2D(0.5f, 0.5f));
    }
    Y += ScoreInkSu + ScoreGapSu;
    if (OutcomeText) {
      FText Outcome;
      if (Model.bAttackerWins) {
        FFormatNamedArguments A;
        A.Add(TEXT("fighter"), FText::FromString(Model.AttackerName));
        Outcome = UmText::Format(EUmTable::Hud, TEXT("hud.combat.wins"), A);
      } else {
        Outcome = UmText::Get(EUmTable::Hud, TEXT("hud.combat.holds"));
      }
      OutcomeText->SetText(Outcome);
      const float Inset = UmCenterCapInsetSu(28.0f, TEXT("type.title"));
      UmCenterPlace(OutcomeText, P + FVector2D(PadXSu, Y - Inset), FVector2D(W - 2.0f * PadXSu, OutcomeInkSu + Inset + 6.0f), 1);
    }
    Y += OutcomeInkSu;
    if (PlanNow.Count > 0 || PlanNow.More > 0) Y += OutcomeGapSu;
  }
  // the lines (a pool of 3 rows)
  if (EffectLines) {
    UmCenterPlace(EffectLines, P + FVector2D(0.0f, Y), FVector2D(W, 0.0f), 1, true);
    EffectLines->SetVisibility(PlanNow.Count > 0 ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  }
  const bool bLit = Model.State == EUmCenterState::Effects;
  for (int32 I = 0; I < PoolSize; ++I) {
    USizeBox* Box = LineBoxes.IsValidIndex(I) ? LineBoxes[I].Get() : nullptr;
    if (!Box) continue;
    const int32 Index = PlanNow.First + I;
    const bool bOn = I < PlanNow.Count && Model.Lines.IsValidIndex(Index);
    Box->SetVisibility(bOn ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
    if (!bOn) continue;
    const FUmCenterLine& L = Model.Lines[Index];
    const float H = LineBoxSu(Rows[Index]);
    Box->SetWidthOverride(W);
    Box->SetHeightOverride(H);
    if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->Slot)) S->SetPadding(FMargin(0.0f, I > 0 ? LineGapSu : 0.0f, 0.0f, 0.0f));
    const bool bCurrent = bLit && Index == Model.Current && !L.bCancelled;
    if (UImage* Bar = LineBars[I]) {
      UmCenterShow(Bar, bCurrent);
      UmCenterPlace(Bar, FVector2D(MarkLeftSu, 0.0f), FVector2D(BarWSu, FMath::Min(H, 24.0f)), 0);
    }
    if (US08AnimatedIconWidget* Mark = LineMarks[I]) {
      const bool bStamp = L.bCancelled && L.bStamp;
      UmCenterShow(Mark, bStamp);
      if (bStamp) {
        if (Mark->GetIconId() != FName(TEXT("marker-x-stamp")) && Mark->SetIcon(FName(TEXT("marker-x-stamp")), StampSu, 24)) {
          Mark->SetDisplaySizeSu(StampSu);
        }
        const FString Key = FString::Printf(TEXT("%d:%d"), Model.Seq, Index);
        if (StampPlayed[I] != Key) {
          StampPlayed[I] = Key;
          Mark->SetReducedMotion(IsReduced());
          Mark->PlayAnim(TEXT("appear"));  // the X stamps in 200 ms (04 §2.7)
        }
        UmCenterPlace(Mark, FVector2D(MarkLeftSu, 0.0f), FVector2D(StampSu), 1);
      }
    }
    if (UTextBlock* T = LineTexts[I]) {
      T->SetText(FText::FromString(Fitted[Index]));
      T->SetColorAndOpacity(FSlateColor(Theme.Color(bCurrent ? TEXT("text.primary") : TEXT("text.secondary"))));
      T->SetLineHeightPercentage(Rows[Index] > 1 ? RowPitchSu / (1.172f * BodySu) : 1.0f);
      T->SetToolTipText(Ellipsis[Index] ? FText::FromString(L.Display()) : FText::GetEmpty());
      T->SetVisibility(Ellipsis[Index] ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible);
      UmCenterPlace(T, FVector2D(TextLeftSu, 2.0f), FVector2D(Column, H - 2.0f), 2);
    }
    ShownTexts.Add(Fitted[Index]);
    if (Ellipsis[Index]) ++EllipsisCount;
  }
  // «ещё {n}»
  const bool bMore = PlanNow.More > 0;
  UmCenterShow(MoreChip, bMore);
  if (bMore) {
    float LinesH = 0.0f;
    for (int32 I = 0; I < PlanNow.Count; ++I) LinesH += (I > 0 ? LineGapSu : 0.0f) + LineBoxSu(Rows[PlanNow.First + I]);
    const float ChipY = Y + LinesH + (PlanNow.Count > 0 ? LineGapSu : 0.0f);
    FText More;
    {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(PlanNow.More));
      More = UmText::Format(EUmTable::Hud, TEXT("hud.combat.effects.more"), A);
    }
    if (MoreText) MoreText->SetText(More);
    if (MoreChip) {
      MoreChip->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg.inset")), Theme.RadiusSu(TEXT("radius.s"))));
      // the chip is never cut: its width is the text's + 2 x 8 su (HB-29 fix1)
      const float ChipW = FMath::CeilToFloat(UmDeckRow::MeasureSu(More.ToString(), 14.0f, FName(TEXT("type.tag")))) + 2.0f * ChipPadSu;
      UmCenterPlace(MoreChip, P + FVector2D(TextLeftSu, ChipY), FVector2D(ChipW, ChipHSu), 2);
    }
  }
  Step();
}

void UUmHudCombatCenter::Step() {
  using namespace UmHudCombatCenter;
  if (!ScoreText) return;
  if (SlamStartMs < 0.0) {
    if (ScoreScaleNow != 1.0f) {
      ScoreScaleNow = 1.0f;
      ScoreText->SetRenderScale(FVector2D(1.0f));
      ScoreText->SetRenderOpacity(1.0f);
    }
    return;
  }
  const float T = static_cast<float>(NowMs() - SlamStartMs);
  if (IsReduced()) {
    ScoreScaleNow = 1.0f;
    ScoreText->SetRenderScale(FVector2D(1.0f));
    ScoreText->SetRenderOpacity(FMath::Clamp(T / 100.0f, 0.0f, 1.0f));
    if (T >= 100.0f) SlamStartMs = -1.0;
    return;
  }
  const float Len = SlamMs * FMath::Max(0.0f, Frame.SpeedMul);
  const float K = Len > 0.0f ? FMath::Clamp(T / Len, 0.0f, 1.0f) : 1.0f;
  ScoreScaleNow = FMath::Lerp(SlamFromScale, 1.0f, 1.0f - FMath::Square(1.0f - K));
  ScoreText->SetRenderScale(FVector2D(ScoreScaleNow));
  ScoreText->SetRenderOpacity(1.0f);
  if (K >= 1.0f) SlamStartMs = -1.0;
}

void UUmHudCombatCenter::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (SlamStartMs >= 0.0) Step();
}

void UUmHudCombatCenter::CollectShotLines(TArray<FString>& Out) const {
  using namespace UmHudCombatCenter;
  if (!bHasModel || Model.State == EUmCenterState::Hidden) return;
  const bool bVisible = Model.State != EUmCenterState::Read && UmGameHudSlots::ShownByProperty(this);
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  const FBox2D R = PanelRectSu();
  if (bVisible && R.bIsValid) Rect = FS08ScreenRect(R.Min.X * Px, R.Min.Y * Px, R.Max.X * Px, R.Max.Y * Px);
  int32 Cancelled = 0;
  for (const FUmCenterLine& L : Model.Lines) Cancelled += L.bCancelled ? 1 : 0;
  const bool bWithScore = Model.bScore && (Model.State == EUmCenterState::Slam || Model.State == EUmCenterState::Hit);
  const FString Extra = FString::Printf(
      TEXT("class=%s h=%.0f lines=%d shown=%d more=%d cancelled=%d current=%d ellipsis=%d score=%s outcome=%s seq=%d"),
      Frame.bClassS ? TEXT("S") : TEXT("L"), PlanNow.HeightSu, Model.Lines.Num(), PlanNow.Count, PlanNow.More, Cancelled,
      Model.Current, EllipsisCount,
      bWithScore ? *FString::Printf(TEXT("%d:%d"), Model.AttackValue, Model.DefenseValue) : TEXT("-"),
      bWithScore ? (Model.bAttackerWins ? TEXT("wins") : TEXT("holds")) : TEXT("-"), Model.Seq);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-COMBAT"), TEXT("umg"), StateName(Model.State), FString(), Rect,
                                        bVisible && !Rect.IsEmpty(), bVisible, SourceName(), Extra));
}

// VS-7 S4 SC-24...SC-30: one PAUSE settings row - see UmSettingRow.h.
#include "UmSettingRow.h"

#include "../S08AnimatedIconWidget.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHeroCard.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"

using namespace UmSettingRow;
using UmRoomUi::MeasureW;
using UmRoomUi::Place;
using UmRoomUi::Style;
using UmRoomUi::Vis;

bool FUmSettingRowModel::operator==(const FUmSettingRowModel& O) const {
  if (Key != O.Key || Kind != O.Kind || !Label.EqualTo(O.Label) || Value != O.Value || Min != O.Min || Max != O.Max ||
      Step != O.Step || MuteKey != O.MuteKey || bMuted != O.bMuted || !Note.EqualTo(O.Note) || bOn != O.bOn ||
      Selected != O.Selected || bSample != O.bSample || bSampleChip != O.bSampleChip || bClassS != O.bClassS ||
      Chips.Num() != O.Chips.Num() || ChipValues != O.ChipValues) {
    return false;
  }
  for (int32 I = 0; I < Chips.Num(); ++I) {
    if (!Chips[I].EqualTo(O.Chips[I])) return false;
  }
  return true;
}

namespace UmSettingRow {
int32 ValueAtX(const FUmSettingRowModel& M, float X, float TrackW) {
  const int32 Span = FMath::Max(1, M.Max - M.Min);
  const float T = FMath::Clamp((X - ControlXSu) / FMath::Max(1.0f, TrackW), 0.0f, 1.0f);
  const int32 Step = FMath::Max(1, M.Step);
  const int32 Raw = M.Min + FMath::RoundToInt(T * Span / Step) * Step;
  return FMath::Clamp(Raw, M.Min, M.Max);
}

float ThumbX(const FUmSettingRowModel& M, int32 V, float InTrackW) {
  const int32 Span = FMath::Max(1, M.Max - M.Min);
  return ControlXSu + InTrackW * FMath::Clamp(static_cast<float>(V - M.Min) / Span, 0.0f, 1.0f);
}

FText Percent(int32 V) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("n"), FText::AsNumber(V));
  return UmText::Format(EUmTable::Screens, TEXT("settings.value.percent"), Args);
}
}  // namespace UmSettingRow

namespace {
/** Word wrap at WrapSu (the line count of a label), measured in Font. */
int32 UmSrLines(const FText& Text, const TCHAR* Type, float WrapSu) {
  TArray<FString> Words;
  Text.ToString().ParseIntoArrayWS(Words);
  int32 Lines = Words.Num() > 0 ? 1 : 0;
  FString Line;
  for (const FString& W : Words) {
    const FString Try = Line.IsEmpty() ? W : Line + TEXT(" ") + W;
    if (Line.IsEmpty() || MeasureW(FText::FromString(Try), Type) <= WrapSu) {
      Line = Try;
    } else {
      ++Lines;
      Line = W;
    }
  }
  return FMath::Max(1, Lines);
}

UBorder* UmSrBorder(UWidgetTree& Tree, UCanvasPanel* Parent, const TCHAR* Name) {
  UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
  B->SetVisibility(ESlateVisibility::HitTestInvisible);
  B->SetPadding(FMargin(0.0f));
  B->SetBrush(FSlateNoResource());
  Parent->AddChild(B);
  return B;
}

UTextBlock* UmSrText(UWidgetTree& Tree, UCanvasPanel* Parent, const TCHAR* Name) {
  UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
  T->SetVisibility(ESlateVisibility::HitTestInvisible);
  Parent->AddChild(T);
  return T;
}

void UmSrSkin(UBorder* B, const TCHAR* Key, float Px) {
  if (!B) return;
  if (const FSlateBrush* S = UUmHudTheme::Get().SkinFor(FName(Key), Px)) B->SetBrush(*S);
}
}  // namespace

bool UUmSettingRow::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) Build();
  return bFirst;
}

void UUmSettingRow::Build() {
  UWidgetTree& Tree = *WidgetTree;
  Canvas = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("RowCanvas")));
  Canvas->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  Tree.RootWidget = Canvas;
  Label = UmSrText(Tree, Canvas, TEXT("Label"));
  Track = UmSrBorder(Tree, Canvas, TEXT("Slider"));
  Fill = UmSrBorder(Tree, Canvas, TEXT("SliderFill"));
  Thumb = UmSrBorder(Tree, Canvas, TEXT("SliderThumb"));
  Value = UmSrText(Tree, Canvas, TEXT("Value"));
  Box = UmSrBorder(Tree, Canvas, TEXT("Check"));
  BoxCheck = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("CheckGlyph")));
  BoxCheck->SetVisibility(ESlateVisibility::HitTestInvisible);
  Canvas->AddChild(BoxCheck);
  BoxText = UmSrText(Tree, Canvas, TEXT("CheckText"));
  MuteBox = UmSrBorder(Tree, Canvas, TEXT("Mute"));
  MuteCheck = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("MuteGlyph")));
  MuteCheck->SetVisibility(ESlateVisibility::HitTestInvisible);
  Canvas->AddChild(MuteCheck);
  MuteText = UmSrText(Tree, Canvas, TEXT("MuteText"));
  Note = UmSrText(Tree, Canvas, TEXT("Note"));
  SampleBox = UmSrBorder(Tree, Canvas, TEXT("KeyHintSample"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  Sample = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("KeyHintSampleButton")));
  Sample->SetVisibility(ESlateVisibility::HitTestInvisible);  // a preview, not a button of the modal (ВР-VS5-SC29-01)
  Canvas->AddChild(Sample);
  Style(Label, TEXT("type.body"), TEXT("text.primary"));
  Label->SetAutoWrapText(true);
  Style(Value, TEXT("type.body"), TEXT("text.primary"));
  Value->SetJustification(ETextJustify::Right);
  Style(BoxText, TEXT("type.body"), TEXT("text.secondary"));
  Style(MuteText, TEXT("type.caption"), TEXT("text.secondary"));
  MuteText->SetAutoWrapText(true);
  Style(Note, TEXT("type.caption"), TEXT("text.secondary"));
  Note->SetAutoWrapText(true);
  UmRoomUi::Icon(BoxCheck, TEXT("ui-check"), BoxSu);   // IC-57 (ВР-VS7-27): the tick over check.on
  UmRoomUi::Icon(MuteCheck, TEXT("ui-check"), BoxSu);
  SetVisibility(ESlateVisibility::Visible);  // the row takes the press of its track and boxes
}

void UUmSettingRow::SetInput(FName InPressPrefix, const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  PressPrefix = InPressPrefix;
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
}

void UUmSettingRow::EnsureChips(int32 Count) {
  if (!WidgetTree || !Canvas) return;
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  while (Chips.Num() < Count) {
    const int32 Index = Chips.Num();
    UUmButton* B = WidgetTree->ConstructWidget<UUmButton>(ButtonClass, FName(*FString::Printf(TEXT("Chip%d"), Index)));
    Canvas->AddChild(B);
    Chips.Add(B);
  }
  for (int32 I = 0; I < Chips.Num(); ++I) {
    UUmButton* B = Chips[I];
    if (!B) continue;
    Vis(B, I < Count, true);
    const FName Id(*FString::Printf(TEXT("%s.%s.%d"), *PressPrefix.ToString(), *Model.Key.ToString(), I));
    if (B->GetPressId() != Id) {
      TWeakObjectPtr<UUmSettingRow> WeakThis(this);
      B->SetPress(Id, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, I](const FS09HudPressOutcome& O) {
        if (UUmSettingRow* Self = WeakThis.Get()) Self->OnChip(I, O);
      }));
    }
  }
}

float UUmSettingRow::Apply(const FUmSettingRowModel& InModel, float PxPerSu) {
  if (bHasModel && Model == InModel && FMath::IsNearlyEqual(Px, PxPerSu) && !bDragging) return HeightSu;
  Model = InModel;
  bHasModel = true;
  Px = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  if (!bDragging) DragValue = Model.Value;
  const bool bSlider = Model.Kind == EUmSettingKind::Slider;
  const bool bCheck = Model.Kind == EUmSettingKind::Check;
  const bool bChips = Model.Kind == EUmSettingKind::Chips;
  if (Label) Label->SetText(Model.Label);
  Vis(Track, bSlider);
  Vis(Fill, bSlider);
  Vis(Thumb, bSlider);
  Vis(Value, bSlider);
  UmSrSkin(Track, TEXT("slider.track"), Px);
  // ВР-VS5-SC24-02: the fill is card.cream (the progress.fill skin is state.pending in the HB-08 set)
  if (Fill) Fill->SetBrush(FSlateRoundedBoxBrush(UUmHudTheme::Get().Color(TEXT("card.cream")), 4.0f));
  UmSrSkin(Thumb, TEXT("slider.thumb"), Px);
  Vis(Box, bCheck);
  Vis(BoxText, bCheck);
  Vis(BoxCheck, bCheck && Model.bOn);
  UmSrSkin(Box, Model.bOn ? TEXT("check.on") : TEXT("check.off"), Px);
  if (BoxText) BoxText->SetText(UmRoomUi::S(Model.bOn ? TEXT("settings.value.on") : TEXT("settings.value.off")));
  const bool bMute = bSlider && !Model.MuteKey.IsNone();
  Vis(MuteBox, bMute);
  Vis(MuteText, bMute);
  Vis(MuteCheck, bMute && Model.bMuted);
  UmSrSkin(MuteBox, Model.bMuted ? TEXT("check.on") : TEXT("check.off"), Px);
  if (MuteText) MuteText->SetText(UmRoomUi::S(TEXT("settings.sound.mute")));
  Vis(Note, !Model.Note.IsEmpty());
  if (Note) Note->SetText(Model.Note);
  EnsureChips(bChips ? Model.Chips.Num() : 0);
  for (int32 I = 0; bChips && I < Model.Chips.Num(); ++I) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.Label = Model.Chips[I];
    B.bSelected = I == Model.Selected;
    B.HeightSu = ChipHSu;
    B.MinWidthSu = 1.0f;
    B.PadXSu = ChipPadSu;
    Chips[I]->ApplyModel(B);
  }
  Vis(SampleBox, bChips && Model.bSample);
  Vis(Sample, bChips && Model.bSample);
  UmSrSkin(SampleBox, TEXT("panel.inset"), Px);
  if (Sample && Model.bSample) {
    FUmButtonModel S;
    S.Variant = EUmButtonVariant::Disc;
    S.IconName = FName(TEXT("action-end-turn"));
    S.Label = Model.bClassS ? FText::GetEmpty() : UmText::Get(EUmTable::Hud, TEXT("hud.action.end_turn"));
    S.KeyHint = Model.bSampleChip ? UmText::Get(EUmTable::Hud, TEXT("hud.key.end_turn")) : FText::GetEmpty();
    S.DiscSu = Model.bClassS ? 40.0f : 48.0f;
    S.HeightSu = Model.bClassS ? 48.0f : 72.0f;
    S.MinWidthSu = Model.bClassS ? 48.0f : 86.0f;
    S.bOwnerTooltip = true;
    Sample->ApplyModel(S);
  }
  ShowValue(bDragging ? DragValue : Model.Value);
  Layout();
  return HeightSu;
}

void UUmSettingRow::ShowValue(int32 V) {
  if (Value) Value->SetText(Percent(V));
  const float Cx = ThumbX(Model, V, TrackW);
  Place(Fill, FVector2D(ControlXSu, BandCySu - 4.0f), FVector2D(FMath::Max(0.0f, Cx - ControlXSu), 8.0f));
  Place(Thumb, FVector2D(Cx - 0.5f * ThumbSu, BandCySu - 0.5f * ThumbSu), FVector2D(ThumbSu, ThumbSu));
}

void UUmSettingRow::Layout() {
  const bool bChips = Model.Kind == EUmSettingKind::Chips;
  ChipRects.Reset();
  SampleRect = FBox2D(ForceInit);
  if (!bChips) {
    // the label wraps in its 140 su column; the control band is 48 su, a long label grows the row
    // ВР-VS7-48: a word longer than the 140 su column (the pseudo-locale) puts the label on its own line above the band
    TArray<FString> Words;
    Model.Label.ToString().ParseIntoArrayWS(Words);
    float LongestWord = 0.0f;
    for (const FString& Wd : Words) LongestWord = FMath::Max(LongestWord, MeasureW(FText::FromString(Wd), TEXT("type.body")));
    bLabelAbove = LongestWord > LabelWSu - 2.0f;
    const float LabelW = bLabelAbove ? WidthSu - ScrollGutterSu : LabelWSu;
    const int32 Lines = UmSrLines(Model.Label, TEXT("type.body"), LabelW);
    LabelHSu = Lines * LineSu;
    if (Label) Label->SetWrapTextAt(LabelW);
    float Cy = PadSu + 0.5f * BandSu;
    if (bLabelAbove) {
      Place(Label, FVector2D(0.0f, PadSu), FVector2D(LabelW, LabelHSu + 2.0f));
      Cy = PadSu + LabelHSu + 4.0f + 0.5f * BandSu;
      HeightSu = PadSu + LabelHSu + 4.0f + BandSu + PadSu;
    } else {
      const float Band = FMath::Max(BandSu, LabelHSu);
      HeightSu = PadSu + Band + PadSu;
      Cy = PadSu + 0.5f * Band;
      Place(Label, FVector2D(0.0f, Cy - 0.5f * LabelHSu), FVector2D(LabelWSu, LabelHSu + 2.0f));
    }
    BandCySu = Cy;
    // ВР-VS7-46: the value box and the mute / note block keep their texts whole; the track takes what is left (>= 120 su)
    ValueW = ValueWSu;
    float BlockW = 0.0f;
    const FText MuteLabel = UmRoomUi::S(TEXT("settings.sound.mute"));
    if (Model.Kind == EUmSettingKind::Slider) {
      ValueW = FMath::Max(ValueWSu, FMath::CeilToFloat(FMath::Max(MeasureW(Percent(Model.Value), TEXT("type.body")),
                                                                  MeasureW(Percent(Model.Max), TEXT("type.body")))) + 2.0f);
      if (!Model.MuteKey.IsNone()) {
        TArray<FString> MuteWords;
        MuteLabel.ToString().ParseIntoArrayWS(MuteWords);
        float Longest = 0.0f;
        for (const FString& Wd : MuteWords) Longest = FMath::Max(Longest, MeasureW(FText::FromString(Wd), TEXT("type.caption")));
        const float Whole = MeasureW(MuteLabel, TEXT("type.caption"));
        BlockW = BoxSu + GapSu + FMath::CeilToFloat(FMath::Max(Longest, FMath::Min(Whole, 60.0f))) + ScrollGutterSu;
      } else if (!Model.Note.IsEmpty()) {
        BlockW = FMath::CeilToFloat(MeasureW(Model.Note, TEXT("type.caption"))) + 2.0f;
      }
    }
    const float DefaultAfter = ControlXSu + TrackWSu + GapSu + ValueWSu + GapSu;  // 420
    TrackW = FMath::Clamp(WidthSu - ControlXSu - GapSu - ValueW - GapSu - BlockW, 120.0f, TrackWSu);
    if (ValueW <= ValueWSu && BlockW <= WidthSu - DefaultAfter + 0.5f) TrackW = TrackWSu;
    AfterX = ControlXSu + TrackW + GapSu + ValueW + GapSu;
    Place(Track, FVector2D(ControlXSu, Cy - 4.0f), FVector2D(TrackW, 8.0f));
    Place(Value, FVector2D(ControlXSu + TrackW + GapSu, Cy - 0.5f * LineSu), FVector2D(ValueW, LineSu + 2.0f));
    Place(MuteBox, FVector2D(AfterX, Cy - 0.5f * BoxSu), FVector2D(BoxSu, BoxSu));
    Place(MuteCheck, FVector2D(AfterX, Cy - 0.5f * BoxSu), FVector2D(BoxSu, BoxSu));
    const float MuteW = WidthSu - ScrollGutterSu - AfterX - BoxSu - GapSu;  // ВР-VS5-SC24-02: the 60 su slot
    if (MuteText) MuteText->SetWrapTextAt(MuteW);
    const float MuteH = MeasureW(MuteLabel, TEXT("type.caption")) > MuteW + 0.5f ? 2.0f * CaptionLineSu : CaptionLineSu;
    Place(MuteText, FVector2D(AfterX + BoxSu + GapSu, Cy - 0.5f * MuteH), FVector2D(MuteW, MuteH + 2.0f));
    if (Model.Kind == EUmSettingKind::Slider) {
      Place(Note, FVector2D(AfterX, Cy - 0.5f * CaptionLineSu), FVector2D(WidthSu - AfterX, CaptionLineSu + 2.0f));
    }
    Place(Box, FVector2D(ControlXSu, Cy - 0.5f * BoxSu), FVector2D(BoxSu, BoxSu));
    Place(BoxCheck, FVector2D(ControlXSu, Cy - 0.5f * BoxSu), FVector2D(BoxSu, BoxSu));
    Place(BoxText, FVector2D(ControlXSu + BoxSu + GapSu, Cy - 0.5f * LineSu), FVector2D(WidthSu - ControlXSu - BoxSu - GapSu, LineSu + 2.0f));
    ShowValue(bDragging ? DragValue : Model.Value);
    return;
  }
  // chips: the label line, the chips (wrapping), the note; the SC-29 sample at the right
  const float SampleW = Model.bSample ? (Model.bClassS ? 48.0f : 86.0f) + 2.0f * GapSu : 0.0f;
  const float SampleH = Model.bSample ? (Model.bClassS ? 48.0f : 72.0f) + 2.0f * GapSu : 0.0f;
  const float Avail = WidthSu - (Model.bSample ? SampleW + 16.0f : 0.0f);
  const int32 Lines = UmSrLines(Model.Label, TEXT("type.body"), Avail);
  LabelHSu = Lines * LineSu;
  Place(Label, FVector2D(0.0f, PadSu), FVector2D(Avail, LabelHSu + 2.0f));
  if (Label) Label->SetWrapTextAt(Avail);
  float X = 0.0f;
  float Y = PadSu + LabelHSu + GapSu;
  ChipsYSu = Y;
  ChipLines = Model.Chips.Num() > 0 ? 1 : 0;
  for (int32 I = 0; I < Model.Chips.Num() && I < Chips.Num(); ++I) {
    const float W = FMath::CeilToFloat(MeasureW(FText::FromString(Model.Chips[I].ToString().ToUpper()), TEXT("type.button"))) + 2.0f * ChipPadSu + 10.0f;  // + the skin edge and the glyph overhang
    if (X > 0.0f && X + W > Avail) {  // ВР-VS5-SC26-03: a chips line past the column wraps
      X = 0.0f;
      Y += ChipHSu + GapSu;
      ++ChipLines;
    }
    Place(Chips[I], FVector2D(X, Y), FVector2D(W, ChipHSu));
    ChipRects.Add(FBox2D(FVector2D(X, Y), FVector2D(X + W, Y + ChipHSu)));
    X += W + GapSu;
  }
  float Bottom = Y + ChipHSu;
  if (!Model.Note.IsEmpty()) {
    const int32 NoteLines = UmSrLines(Model.Note, TEXT("type.caption"), Avail);
    if (Note) Note->SetWrapTextAt(Avail);
    Place(Note, FVector2D(0.0f, Bottom + GapSu), FVector2D(Avail, NoteLines * CaptionLineSu + 2.0f));
    Bottom += GapSu + NoteLines * CaptionLineSu;
  }
  if (Model.bSample) {
    const FVector2D Min(WidthSu - SampleW, PadSu);
    SampleRect = FBox2D(Min, Min + FVector2D(SampleW, SampleH));
    Place(SampleBox, Min, FVector2D(SampleW, SampleH));
    Place(Sample, Min + FVector2D(GapSu, GapSu), FVector2D(SampleW - 2.0f * GapSu, SampleH - 2.0f * GapSu));
    Bottom = FMath::Max(Bottom, PadSu + SampleH);
  }
  HeightSu = Bottom + PadSu;
}

FString UUmSettingRow::GetLabelText() const { return Label ? Label->GetText().ToString() : FString(); }
FString UUmSettingRow::GetValueText() const {
  if (Model.Kind == EUmSettingKind::Slider) return Value ? Value->GetText().ToString() : FString();
  if (Model.Kind == EUmSettingKind::Check) return BoxText ? BoxText->GetText().ToString() : FString();
  return Model.Chips.IsValidIndex(Model.Selected) ? Model.Chips[Model.Selected].ToString() : FString();
}
FString UUmSettingRow::GetNoteText() const { return Note && !Model.Note.IsEmpty() ? Note->GetText().ToString() : FString(); }
bool UUmSettingRow::IsSampleShown() const { return Sample && Sample->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmSettingRow::IsSampleChipShown() const { return IsSampleShown() && !Sample->GetModel().KeyHint.IsEmpty(); }

bool UUmSettingRow::LayoutFits(FString* OutWhy) const {
  auto Bad = [OutWhy](const FString& Why) {
    if (OutWhy) *OutWhy = Why;
    return false;
  };
  if (Model.Kind == EUmSettingKind::Chips) {
    for (int32 I = 0; I < ChipRects.Num(); ++I) {
      const FBox2D& R = ChipRects[I];
      if (R.Max.X > WidthSu + 0.5f) return Bad(FString::Printf(TEXT("chip %d past 520 su (%.0f)"), I, R.Max.X));
      if (SampleRect.bIsValid && R.Intersect(SampleRect)) return Bad(FString::Printf(TEXT("chip %d under the sample"), I));
      if (R.Min.Y < PadSu + LabelHSu) return Bad(FString::Printf(TEXT("chip %d over the label"), I));
    }
    return true;
  }
  // slider / check: the value word and the mute caption fit their boxes
  if (!bLabelAbove) {
    TArray<FString> Words;
    Model.Label.ToString().ParseIntoArrayWS(Words);
    for (const FString& Wd : Words) {
      if (MeasureW(FText::FromString(Wd), TEXT("type.body")) > LabelWSu + 0.5f) return Bad(TEXT("label word past its column"));
    }
  }
  if (Model.Kind == EUmSettingKind::Slider) {
    if (MeasureW(Percent(Model.Value), TEXT("type.body")) > ValueW + 0.5f) return Bad(TEXT("value past its box"));
    if (TrackW < 119.5f) return Bad(TEXT("track under 120 su"));
    if (!Model.MuteKey.IsNone()) {
      const FText MuteLabel = UmRoomUi::S(TEXT("settings.sound.mute"));
      TArray<FString> Words;
      MuteLabel.ToString().ParseIntoArrayWS(Words);
      const float MuteW = WidthSu - ScrollGutterSu - AfterX - BoxSu - GapSu;  // ВР-VS5-SC24-02: the 60 su slot
      for (const FString& Wd : Words) {
        if (MeasureW(FText::FromString(Wd), TEXT("type.caption")) > MuteW + 0.5f) return Bad(TEXT("mute caption past 520 su"));
      }
      if (MeasureW(MuteLabel, TEXT("type.caption")) > 2.0f * MuteW + 0.5f) return Bad(TEXT("mute caption over 2 lines"));
    }
    if (!Model.Note.IsEmpty() && MeasureW(Model.Note, TEXT("type.caption")) > WidthSu - AfterX + 0.5f) return Bad(TEXT("note past 520 su"));
  }
  return true;
}

// ------------------------------------------------------------------------------------------------ input

FVector2D UUmSettingRow::LocalSu(const FGeometry& G, const FPointerEvent& E) const {
  return G.AbsoluteToLocal(E.GetScreenSpacePosition());  // the row is laid out in su: local units are su
}

void UUmSettingRow::Sound(const TCHAR* Bank) {
  if (Input.OnSound) Input.OnSound(FName(Bank));
}

void UUmSettingRow::Commit(FName Key, const FString& V) {
  if (Input.OnCommit) Input.OnCommit(Key, V);
}

FReply UUmSettingRow::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !bHasModel) return FReply::Unhandled();
  const FVector2D P = LocalSu(InGeometry, InMouseEvent);
  const bool bBand = FMath::Abs(P.Y - BandCySu) <= 0.5f * BandSu;
  if (Model.Kind == EUmSettingKind::Slider && bBand) {
    if (P.X >= ControlXSu - ThumbSu && P.X <= ControlXSu + TrackW + ThumbSu) {
      bDragging = true;
      DragValue = ValueAtX(Model, P.X, TrackW);
      ShowValue(DragValue);
      return FReply::Handled().CaptureMouse(TakeWidget());
    }
    if (!Model.MuteKey.IsNone() && P.X >= AfterX && P.X <= WidthSu) {
      SimulateToggle(true);
      return FReply::Handled();
    }
  }
  if (Model.Kind == EUmSettingKind::Check && bBand && P.X >= ControlXSu - 4.0f && P.X <= ControlXSu + BoxSu + GapSu + 80.0f) {
    SimulateToggle(false);
    return FReply::Handled();
  }
  return FReply::Handled();  // the modal keeps the press (04 §1)
}

FReply UUmSettingRow::NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (!bDragging) return FReply::Unhandled();
  const int32 V = ValueAtX(Model, LocalSu(InGeometry, InMouseEvent).X, TrackW);
  if (V != DragValue) {
    if (TickBand(V) != TickBand(DragValue)) Sound(TEXT("UI-SLIDER-TICK"));  // every 10 % (08 hooks SC-25)
    DragValue = V;
    ShowValue(DragValue);
  }
  return FReply::Handled();
}

FReply UUmSettingRow::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (!bDragging) return FReply::Unhandled();
  bDragging = false;
  if (DragValue != Model.Value) {
    Model.Value = DragValue;
    Commit(Model.Key, FString::FromInt(DragValue));  // applied on the release (04 §1.8)
  }
  return FReply::Handled().ReleaseMouseCapture();
}

void UUmSettingRow::NativeOnMouseCaptureLost(const FCaptureLostEvent& CaptureLostEvent) {
  Super::NativeOnMouseCaptureLost(CaptureLostEvent);
  if (!bDragging) return;
  bDragging = false;
  if (DragValue != Model.Value) {
    Model.Value = DragValue;
    Commit(Model.Key, FString::FromInt(DragValue));
  }
}

void UUmSettingRow::SimulateDrag(int32 ToValue) {
  if (Model.Kind != EUmSettingKind::Slider) return;
  const int32 Step = FMath::Max(1, Model.Step);
  int32 V = Model.Value;
  const int32 Target = FMath::Clamp(ToValue, Model.Min, Model.Max);
  bDragging = true;
  while (V != Target) {
    const int32 Next = V < Target ? FMath::Min(V + Step, Target) : FMath::Max(V - Step, Target);
    if (TickBand(Next) != TickBand(V)) Sound(TEXT("UI-SLIDER-TICK"));
    V = Next;
  }
  DragValue = V;
  ShowValue(V);
  bDragging = false;
  if (V != Model.Value) {
    Model.Value = V;
    Commit(Model.Key, FString::FromInt(V));
  }
}

void UUmSettingRow::SimulateToggle(bool bMute) {
  if (bMute) {
    if (Model.MuteKey.IsNone()) return;
    Sound(TEXT("UI-TOGGLE"));
    Commit(Model.MuteKey, Model.bMuted ? TEXT("0") : TEXT("1"));
    return;
  }
  if (Model.Kind != EUmSettingKind::Check) return;
  Sound(TEXT("UI-TOGGLE"));
  Commit(Model.Key, Model.bOn ? TEXT("0") : TEXT("1"));
}

void UUmSettingRow::SimulateChip(int32 Index) {
  if (!Model.ChipValues.IsValidIndex(Index) || Index == Model.Selected) return;
  Sound(TEXT("UI-TOGGLE"));
  Commit(Model.Key, Model.ChipValues[Index]);
}

void UUmSettingRow::OnChip(int32 Index, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act) return;
  SimulateChip(Index);
}

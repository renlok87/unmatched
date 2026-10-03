// Art Tuner M3: the Slate panel (S08ArtTunerPanel.h).
#include "S08ArtTunerPanel.h"

#include "S08ArtTuner.h"
#include "Dom/JsonValue.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformTime.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SExpandableArea.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace {
const FLinearColor GTextColor(0.9f, 0.92f, 0.97f);
const FLinearColor GDimColor(0.62f, 0.66f, 0.74f);
const FLinearColor GChangedColor(1.0f, 0.68f, 0.25f);
const FLinearColor GNoteColor(1.0f, 0.78f, 0.4f);
const FLinearColor GErrorColor(1.0f, 0.42f, 0.38f);
const FLinearColor GOkColor(0.5f, 0.9f, 0.6f);
const FLinearColor GBarColor(0.32f, 0.36f, 0.46f);
constexpr float LabelWidth = 168.0f;
constexpr float FieldWidth = 64.0f;
constexpr float UnitWidth = 54.0f;

FSlateFontInfo PanelFont(int32 Size, bool bBold = false) {
  return FCoreStyle::GetDefaultFontStyle(bBold ? "Bold" : "Regular", Size);
}

TSharedRef<SWidget> SmallButton(const FText& Label, const FText& Tip, TFunction<void()> OnClick) {
  return SNew(SButton)
      .ContentPadding(FMargin(6.0f, 1.0f))
      .ToolTipText(Tip)
      .OnClicked_Lambda([OnClick]() {
        if (OnClick) OnClick();
        return FReply::Handled();
      })[SNew(STextBlock).Font(PanelFont(9)).Text(Label)];
}

double ParseNumber(const FString& In, bool& bOk) {
  double V = 0.0;
  bOk = LexTryParseString(V, *In.TrimStartAndEnd().Replace(TEXT(","), TEXT(".")));
  return V;
}
}  // namespace

void SS08ArtTunerPanel::Construct(const FArguments& InArgs, const TSharedPtr<FS08ArtTunerSession>& InSession,
                                  FS08ArtTunerPanelActions InActions) {
  Session = InSession;
  Actions = MoveTemp(InActions);
  if (InSession.IsValid() && !InSession->Groups.IsEmpty()) Expanded.Add(InSession->Groups[0].Id);
  TSharedPtr<FS08ArtTunerSession> S = InSession;
  const FString Title = S.IsValid() ? FString::Printf(TEXT("Art Tuner · %s · %s"), *S->BoardId, *S->LightId) : FString(TEXT("Art Tuner"));
  ChildSlot[
      SNew(SBorder)
          .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
          .BorderBackgroundColor(FLinearColor(0.025f, 0.03f, 0.042f, 0.9f))
          .Padding(FMargin(10.0f, 8.0f))[
              SNew(SVerticalBox) +
              SVerticalBox::Slot().AutoHeight()[
                  SNew(SHorizontalBox) +
                  SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[
                      SNew(STextBlock).Font(PanelFont(12, true)).ColorAndOpacity(GTextColor).Text(FText::FromString(Title))] +
                  SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
                      SNew(STextBlock).Font(PanelFont(10)).ColorAndOpacity(GChangedColor).Text_Lambda([this]() {
                        const TSharedPtr<FS08ArtTunerSession> P = Session.Pin();
                        const int32 N = P.IsValid() ? P->Model.GetEntries().Num() : 0;
                        return N > 0 ? FText::FromString(FString::Printf(TEXT("● изменено: %d"), N)) : FText::GetEmpty();
                      })]] +
              SVerticalBox::Slot().AutoHeight().Padding(FMargin(0.0f, 6.0f, 0.0f, 2.0f))[
                  SNew(SHorizontalBox) +
                  SHorizontalBox::Slot().AutoWidth().Padding(FMargin(0.0f, 0.0f, 6.0f, 0.0f))[
                      SmallButton(FText::FromString(TEXT("Сохранить (Ctrl+S)")),
                                  FText::FromString(TEXT("Записать изменённые значения в файл S08ArtTuner.overrides.json")),
                                  [this]() {
                                    Flush();
                                    if (Actions.Save) Actions.Save();
                                  })] +
                  SHorizontalBox::Slot().AutoWidth().Padding(FMargin(0.0f, 0.0f, 6.0f, 0.0f))[
                      SmallButton(FText::FromString(TEXT("Отменить всё")),
                                  FText::FromString(TEXT("Все значения к профилю (файл не меняется, пока не нажато «Сохранить»)")),
                                  [this]() {
                                    PendingId.Reset();
                                    if (Actions.ResetGroup) Actions.ResetGroup(FString());
                                  })] +
                  SHorizontalBox::Slot().FillWidth(1.0f)[SNew(SSpacer)] +
                  SHorizontalBox::Slot().AutoWidth()[
                      SmallButton(FText::FromString(TEXT("Закрыть (F10)")), FText::FromString(TEXT("Спрятать панель")), [this]() {
                        Flush();
                        if (Actions.Close) Actions.Close();
                      })]] +
              SVerticalBox::Slot().AutoHeight().Padding(FMargin(0.0f, 0.0f, 0.0f, 6.0f))[
                  SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GDimColor).Text_Lambda([this]() {
                    const TSharedPtr<FS08ArtTunerSession> P = Session.Pin();
                    const FString File = P.IsValid() && !P->File.IsEmpty() ? P->File : FString(TEXT("не задан (-ArtTunerFile)"));
                    return FText::FromString(TEXT("файл: ") + File);
                  })] +
              SVerticalBox::Slot().FillHeight(1.0f)[SAssignNew(Body, SBox)] +
              SVerticalBox::Slot().AutoHeight().Padding(FMargin(0.0f, 6.0f, 0.0f, 0.0f))[
                  SNew(STextBlock)
                      .Font(PanelFont(9))
                      .AutoWrapText(true)
                      .ColorAndOpacity_Lambda([this]() { return StatusColor(); })
                      .Text_Lambda([this]() { return StatusText(); })] +
              SVerticalBox::Slot().AutoHeight().Padding(FMargin(0.0f, 4.0f, 0.0f, 0.0f))[
                  SNew(STextBlock)
                      .Font(PanelFont(8))
                      .ColorAndOpacity(GDimColor)
                      .AutoWrapText(true)
                      .Text(FText::FromString(TEXT("Двигаешь — сцена меняется сразу; группа «пересборка» пересобирает сцену. "
                                                   "● — значение отличается от профиля, × — вернуть одно значение. "
                                                   "Tab — следующий герой, H — подсветка вкл/выкл, F1 — справка.")))]]];
  Rebuild();
}

FString SS08ArtTunerPanel::RowsSignature() const {
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  if (!S.IsValid()) return FString();
  FString Sig = S->BoardId;
  for (const FS08TunerGroup& G : S->Groups) Sig += FString::Printf(TEXT("|%s:%d:%d"), *G.Id, G.Params.Num(), G.bInert ? 1 : 0);
  return Sig;
}

void SS08ArtTunerPanel::Rebuild() {
  Signature = RowsSignature();
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  TSharedRef<SScrollBox> Scroll = SNew(SScrollBox);
  if (S.IsValid()) {
    if (S->Groups.IsEmpty()) {
      Scroll->AddSlot()[SNew(STextBlock).Font(PanelFont(10)).ColorAndOpacity(GErrorColor).AutoWrapText(true).Text(
          FText::FromString(TEXT("Нет строк для этой доски (реестр Config/ArtTuner/S08ArtTunerParams.json не прочитан?)")))];
    }
    for (const FS08TunerGroup& G : S->Groups) {
      Scroll->AddSlot().Padding(FMargin(0.0f, 0.0f, 4.0f, 4.0f))[BuildGroup(G, Expanded.Contains(G.Id))];
    }
  }
  if (Body.IsValid()) Body->SetContent(Scroll);
}

TSharedRef<SWidget> SS08ArtTunerPanel::BuildGroup(const FS08TunerGroup& G, bool bExpanded) {
  const FString GroupId = G.Id;
  TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
  for (const FS08TunerParam& P : G.Params) Rows->AddSlot().AutoHeight().Padding(FMargin(0.0f, 1.0f))[BuildRow(P)];
  const bool bRebuild = G.Scope == ES08TunerScope::Rebuild;
  TSharedRef<SHorizontalBox> Header = SNew(SHorizontalBox);
  Header->AddSlot().AutoWidth().VAlign(VAlign_Center)[
      SNew(STextBlock).Font(PanelFont(10, true)).ColorAndOpacity(G.bInert ? GDimColor : GTextColor).Text(
          FText::FromString(G.Label + (bRebuild && !G.Label.Contains(TEXT("пересборка")) ? TEXT(" (пересборка)") : TEXT(""))))];
  Header->AddSlot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(FMargin(6.0f, 0.0f))[
      SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GNoteColor).AutoWrapText(true).Text(
          FText::FromString(G.bInert ? TEXT("! ") + G.Note : G.Note))];
  Header->AddSlot().AutoWidth().VAlign(VAlign_Center)[
      SmallButton(FText::FromString(TEXT("сбросить")), FText::FromString(TEXT("Значения этой группы к профилю")), [this, GroupId]() {
        PendingId.Reset();
        if (Actions.ResetGroup) Actions.ResetGroup(GroupId);
      })];
  return SNew(SExpandableArea)
      .InitiallyCollapsed(!bExpanded)
      .BorderBackgroundColor(FLinearColor(0.08f, 0.09f, 0.12f, 0.9f))
      .BodyBorderBackgroundColor(FLinearColor(0.04f, 0.045f, 0.06f, 0.6f))
      .OnAreaExpansionChanged_Lambda([this, GroupId](bool bOpen) {
        if (bOpen) Expanded.Add(GroupId);
        else Expanded.Remove(GroupId);
      })
      .HeaderContent()[Header]
      .BodyContent()[SNew(SBox).Padding(FMargin(4.0f, 2.0f))[Rows]];
}

TSharedRef<SWidget> SS08ArtTunerPanel::BuildRow(const FS08TunerParam& P) {
  switch (P.Type) {
    case ES08TunerType::Bool: return RowFrame(P, BuildBoolRow(P));
    case ES08TunerType::ColorSrgb: return RowFrame(P, BuildSrgbRow(P));
    case ES08TunerType::ColorLinear: return RowFrame(P, BuildLinearRow(P));
    case ES08TunerType::Number:
    case ES08TunerType::Ev100:
    default: return RowFrame(P, BuildNumberRow(P));
  }
}

TSharedRef<SWidget> SS08ArtTunerPanel::RowFrame(const FS08TunerParam& P, const TSharedRef<SWidget>& Editor) {
  const FString Id = P.Id;
  FString Tip = P.Pointer;
  if (!P.Note.IsEmpty()) Tip = P.Note + TEXT("\n") + Tip;
  if (P.bHasMin || P.bHasMax) {
    Tip += FString::Printf(TEXT("\nдиапазон: %s … %s"), P.bHasMin ? *S08ArtTuner::FormatNumber(P.Min, 4) : TEXT("—"),
                           P.bHasMax ? *S08ArtTuner::FormatNumber(P.Max, 4) : TEXT("—"));
  }
  return SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(FMargin(0.0f, 3.0f, 0.0f, 0.0f))[
             SNew(SBox).WidthOverride(LabelWidth)[
                 SNew(STextBlock).Font(PanelFont(9)).ColorAndOpacity(GTextColor).ToolTipText(FText::FromString(Tip)).Text(
                     FText::FromString(P.Label))]] +
         SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[Editor] +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(FMargin(4.0f, 2.0f, 0.0f, 0.0f))[
             SNew(SBox).WidthOverride(12.0f)[
                 SNew(STextBlock).Font(PanelFont(10)).ColorAndOpacity(GChangedColor).Text(FText::FromString(TEXT("●")))
                     .Visibility_Lambda([this, Id]() { return IsChanged(Id) ? EVisibility::Visible : EVisibility::Hidden; })]] +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top)[
             SNew(SBox).WidthOverride(34.0f).HeightOverride(20.0f).Visibility_Lambda([this, Id]() {
               return IsChanged(Id) ? EVisibility::Visible : EVisibility::Hidden;
             })[SNew(SButton)
                    .ContentPadding(FMargin(0.0f))
                    .HAlign(HAlign_Center)
                    .VAlign(VAlign_Center)
                    .ToolTipText(FText::FromString(TEXT("Вернуть значение профиля")))
                    .OnClicked_Lambda([this, Id]() {
                      if (PendingId == Id) PendingId.Reset();
                      if (Actions.ResetRow) Actions.ResetRow(Id);
                      return FReply::Handled();
                    })[SNew(STextBlock).Font(PanelFont(10, true)).Text(FText::FromString(TEXT("×")))]]];
}

TSharedRef<SWidget> SS08ArtTunerPanel::BuildNumberRow(const FS08TunerParam& P) {
  const FString Id = P.Id;
  const float Min = static_cast<float>(P.SliderMin);
  const float Max = static_cast<float>(P.SliderMax);
  const int32 Decimals = P.Decimals();
  return SNew(SHorizontalBox) +
         SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[
             SNew(SSlider)
                 .MinValue(Min)
                 .MaxValue(Max)
                 .StepSize(static_cast<float>(P.Step))
                 .MouseUsesStep(true)
                 .SliderBarColor(GBarColor)
                 .Value_Lambda([this, Id, Min, Max]() { return FMath::Clamp(static_cast<float>(NumberOf(Id)), Min, Max); })
                 .OnValueChanged_Lambda([this, Id](float V) { Queue(Id, MakeShared<FJsonValueNumber>(V)); })
                 .OnMouseCaptureEnd_Lambda([this]() { Flush(); })] +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(FMargin(4.0f, 0.0f, 2.0f, 0.0f))[
             SNew(SBox).WidthOverride(FieldWidth)[
                 SNew(SEditableTextBox)
                     .Font(PanelFont(9))
                     .SelectAllTextWhenFocused(true)
                     .Text_Lambda([this, Id, Decimals]() { return FText::FromString(S08ArtTuner::FormatNumber(NumberOf(Id), Decimals)); })
                     .OnTextCommitted_Lambda([this, Id](const FText& Text, ETextCommit::Type Commit) {
                       if (Commit == ETextCommit::OnCleared) return;
                       bool bOk = false;
                       const double V = ParseNumber(Text.ToString(), bOk);
                       if (bOk) Send(Id, MakeShared<FJsonValueNumber>(V));
                       else LocalError = FString::Printf(TEXT("«%s» — не число"), *Text.ToString());
                       if (Commit == ETextCommit::OnEnter) FSlateApplication::Get().SetAllUserFocusToGameViewport();
                     })]] +
         SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
             SNew(SBox).WidthOverride(UnitWidth)[
                 SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GDimColor).Text(FText::FromString(P.Unit))]];
}

TSharedRef<SWidget> SS08ArtTunerPanel::BuildBoolRow(const FS08TunerParam& P) {
  const FString Id = P.Id;
  return SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth()[
      SNew(SCheckBox)
          .IsChecked_Lambda([this, Id]() { return BoolOf(Id) ? ECheckBoxState::Checked : ECheckBoxState::Unchecked; })
          .OnCheckStateChanged_Lambda([this, Id](ECheckBoxState State) {
            Send(Id, MakeShared<FJsonValueBoolean>(State == ECheckBoxState::Checked));
          })];
}

TSharedRef<SWidget> SS08ArtTunerPanel::BuildSrgbRow(const FS08TunerParam& P) {
  const FString Id = P.Id;
  TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
  Box->AddSlot().AutoHeight()[
      SNew(SHorizontalBox) +
      SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(FMargin(0.0f, 0.0f, 6.0f, 0.0f))[
          SNew(SColorBlock).Size(FVector2D(36.0, 16.0)).Color_Lambda([this, Id]() {
            return FLinearColor(FColor::FromHex(HexOf(Id)));
          })] +
      SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
          SNew(SBox).WidthOverride(82.0f)[
              SNew(SEditableTextBox)
                  .Font(PanelFont(9))
                  .SelectAllTextWhenFocused(true)
                  .Text_Lambda([this, Id]() { return FText::FromString(HexOf(Id)); })
                  .OnTextCommitted_Lambda([this, Id](const FText& Text, ETextCommit::Type Commit) {
                    if (Commit == ETextCommit::OnCleared) return;
                    Send(Id, MakeShared<FJsonValueString>(Text.ToString()));
                    if (Commit == ETextCommit::OnEnter) FSlateApplication::Get().SetAllUserFocusToGameViewport();
                  })]]];
  const TCHAR* Names[] = {TEXT("R"), TEXT("G"), TEXT("B")};
  for (int32 C = 0; C < 3; ++C) {
    Box->AddSlot().AutoHeight()[
        SNew(SHorizontalBox) +
        SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
            SNew(SBox).WidthOverride(14.0f)[SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GDimColor).Text(FText::FromString(Names[C]))]] +
        SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[
            SNew(SSlider)
                .MinValue(0.0f)
                .MaxValue(255.0f)
                .StepSize(1.0f)
                .MouseUsesStep(true)
                .SliderBarColor(GBarColor)
                .Value_Lambda([this, Id, C]() {
                  const FColor Col = FColor::FromHex(HexOf(Id));
                  return static_cast<float>(C == 0 ? Col.R : C == 1 ? Col.G : Col.B);
                })
                .OnValueChanged_Lambda([this, Id, C](float V) {
                  FColor Col = FColor::FromHex(HexOf(Id));
                  const uint8 B = static_cast<uint8>(FMath::Clamp(FMath::RoundToInt(V), 0, 255));
                  (C == 0 ? Col.R : C == 1 ? Col.G : Col.B) = B;
                  Queue(Id, MakeShared<FJsonValueString>(FString::Printf(TEXT("#%02X%02X%02X"), Col.R, Col.G, Col.B)));
                })
                .OnMouseCaptureEnd_Lambda([this]() { Flush(); })] +
        SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
            SNew(SBox).WidthOverride(28.0f)[SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GDimColor).Text_Lambda([this, Id, C]() {
              const FColor Col = FColor::FromHex(HexOf(Id));
              return FText::AsNumber(C == 0 ? Col.R : C == 1 ? Col.G : Col.B);
            })]]];
  }
  return Box;
}

TSharedRef<SWidget> SS08ArtTunerPanel::BuildLinearRow(const FS08TunerParam& P) {
  const FString Id = P.Id;
  const float Max = static_cast<float>(P.SliderMax);
  TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
  Box->AddSlot().AutoHeight()[
      SNew(SColorBlock).Size(FVector2D(36.0, 12.0)).Color_Lambda([this, Id]() {
        const TArray<double> L = LinearOf(Id);
        // a linear colour above 1 is shown at its hue (the swatch is a hint, the numbers are the value)
        const double M = FMath::Max3(L[0], L[1], L[2]);
        const double K = M > 1.0 ? 1.0 / M : 1.0;
        return FLinearColor(static_cast<float>(L[0] * K), static_cast<float>(L[1] * K), static_cast<float>(L[2] * K));
      })];
  const TCHAR* Names[] = {TEXT("R"), TEXT("G"), TEXT("B")};
  for (int32 C = 0; C < 3; ++C) {
    Box->AddSlot().AutoHeight()[
        SNew(SHorizontalBox) +
        SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
            SNew(SBox).WidthOverride(14.0f)[SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GDimColor).Text(FText::FromString(Names[C]))]] +
        SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[
            SNew(SSlider)
                .MinValue(0.0f)
                .MaxValue(Max)
                .StepSize(static_cast<float>(P.Step))
                .MouseUsesStep(true)
                .SliderBarColor(GBarColor)
                .Value_Lambda([this, Id, C, Max]() { return FMath::Clamp(static_cast<float>(LinearOf(Id)[C]), 0.0f, Max); })
                .OnValueChanged_Lambda([this, Id, C](float V) {
                  TArray<double> L = LinearOf(Id);
                  L[C] = V;
                  TArray<TSharedPtr<FJsonValue>> Arr;
                  for (const double X : L) Arr.Add(MakeShared<FJsonValueNumber>(X));
                  Queue(Id, MakeShared<FJsonValueArray>(Arr));
                })
                .OnMouseCaptureEnd_Lambda([this]() { Flush(); })] +
        SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[
            SNew(SBox).WidthOverride(36.0f)[SNew(STextBlock).Font(PanelFont(8)).ColorAndOpacity(GDimColor).Text_Lambda([this, Id, C]() {
              return FText::FromString(S08ArtTuner::FormatNumber(LinearOf(Id)[C], 2));
            })]]];
  }
  return Box;
}

const FS08TunerParam* SS08ArtTunerPanel::Find(const FString& RowId) const {
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  return S.IsValid() ? S->FindParam(RowId) : nullptr;
}

FString SS08ArtTunerPanel::ValuePointer(const FString& RowId) const {
  const FS08TunerParam* P = Find(RowId);
  if (!P) return FString();
  return P->Type == ES08TunerType::Ev100 ? P->Pointer + TEXT("/ev100") : P->Pointer;
}

double SS08ArtTunerPanel::NumberOf(const FString& RowId) const {
  double V = 0.0;
  if (PendingId == RowId && PendingValue.IsValid() && PendingValue->TryGetNumber(V)) return V;
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  if (!S.IsValid()) return 0.0;
  const TSharedPtr<FJsonValue> J = S->Model.Value(ValuePointer(RowId));
  if (J.IsValid()) {
    J->TryGetNumber(V);
  } else if (const FS08TunerParam* P = Find(RowId)) {
    V = P->bHasDefault ? P->DefaultNumber : 0.0;  // an absent optional key
  }
  return V;
}

bool SS08ArtTunerPanel::BoolOf(const FString& RowId) const {
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  const TSharedPtr<FJsonValue> J = S.IsValid() ? S->Model.Value(ValuePointer(RowId)) : nullptr;
  return J.IsValid() && J->Type == EJson::Boolean && J->AsBool();
}

FString SS08ArtTunerPanel::HexOf(const FString& RowId) const {
  if (PendingId == RowId && PendingValue.IsValid() && PendingValue->Type == EJson::String) return PendingValue->AsString();
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  const TSharedPtr<FJsonValue> J = S.IsValid() ? S->Model.Value(ValuePointer(RowId)) : nullptr;
  return J.IsValid() && J->Type == EJson::String ? J->AsString() : FString(TEXT("#FFFFFF"));
}

TArray<double> SS08ArtTunerPanel::LinearOf(const FString& RowId) const {
  TArray<double> Out = {0.0, 0.0, 0.0};
  TSharedPtr<FJsonValue> J;
  if (PendingId == RowId && PendingValue.IsValid() && PendingValue->Type == EJson::Array) {
    J = PendingValue;
  } else {
    const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
    J = S.IsValid() ? S->Model.Value(ValuePointer(RowId)) : nullptr;
  }
  if (J.IsValid() && J->Type == EJson::Array) {
    for (int32 I = 0; I < 3 && I < J->AsArray().Num(); ++I) {
      if (J->AsArray()[I].IsValid()) J->AsArray()[I]->TryGetNumber(Out[I]);
    }
  }
  return Out;
}

bool SS08ArtTunerPanel::IsChanged(const FString& RowId) const {
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  return S.IsValid() && S->Model.IsChanged(ValuePointer(RowId));
}

void SS08ArtTunerPanel::Queue(const FString& RowId, const TSharedPtr<FJsonValue>& Value) {
  if (!PendingId.IsEmpty() && PendingId != RowId) Flush();
  PendingId = RowId;
  PendingValue = Value;
  if (FPlatformTime::Seconds() - LastSent >= 1.0 / S08ArtTunerSpec::ApplyHz) Flush();
}

void SS08ArtTunerPanel::Flush() {
  if (PendingId.IsEmpty()) return;
  const FString Id = PendingId;
  const TSharedPtr<FJsonValue> Value = PendingValue;
  PendingId.Reset();
  PendingValue.Reset();
  Send(Id, Value);
}

void SS08ArtTunerPanel::Send(const FString& RowId, const TSharedPtr<FJsonValue>& Value) {
  LastSent = FPlatformTime::Seconds();
  if (!Actions.Set) return;
  FString Error;
  if (Actions.Set(RowId, Value, Error)) {
    LocalError.Reset();
  } else {
    LocalError = Error;
  }
}

void SS08ArtTunerPanel::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) {
  SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
  if (!PendingId.IsEmpty() && FPlatformTime::Seconds() - LastSent >= 1.0 / S08ArtTunerSpec::ApplyHz) Flush();
  if (RowsSignature() != Signature) Rebuild();
}

FText SS08ArtTunerPanel::StatusText() const {
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  if (!LocalError.IsEmpty()) return FText::FromString(TEXT("Не применено: ") + LocalError);
  if (!S.IsValid()) return FText::GetEmpty();
  if (!S->LastError.IsEmpty()) return FText::FromString(TEXT("Ошибка: ") + S->LastError);
  if (!S->LastSavedAt.IsEmpty()) {
    return FText::FromString(FString::Printf(TEXT("Сохранено в %s · применений %d, пересборок %d, последнее %.1f мс"),
                                             *S->LastSavedAt, S->Applies, S->Rebuilds, S->LastApplyMs));
  }
  if (!S->Warnings.IsEmpty()) {
    return FText::FromString(FString::Printf(TEXT("Предупреждений: %d — %s"), S->Warnings.Num(), *S->Warnings[0]));
  }
  return FText::FromString(FString::Printf(TEXT("Применений %d, пересборок %d, последнее %.1f мс"), S->Applies, S->Rebuilds,
                                           S->LastApplyMs));
}

FSlateColor SS08ArtTunerPanel::StatusColor() const {
  const TSharedPtr<FS08ArtTunerSession> S = Session.Pin();
  if (!LocalError.IsEmpty() || (S.IsValid() && !S->LastError.IsEmpty())) return GErrorColor;
  if (S.IsValid() && !S->LastSavedAt.IsEmpty()) return GOkColor;
  if (S.IsValid() && !S->Warnings.IsEmpty()) return GNoteColor;
  return GDimColor;
}

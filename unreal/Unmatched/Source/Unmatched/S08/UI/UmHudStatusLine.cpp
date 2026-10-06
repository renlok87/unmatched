// VS-2 HB-15: STATUS - see UmHudStatusLine.h.
#include "UmHudStatusLine.h"

#include "../S08IconMotion.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "HAL/PlatformTime.h"
#include "Rendering/SlateRenderer.h"

const TCHAR* const UUmHudStatusLine::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_STATUS");

namespace UmHudStatus {
const TCHAR* StateName(EUmStatusState State) {
  switch (State) {
    case EUmStatusState::Opp: return TEXT("opp");
    case EUmStatusState::Defend: return TEXT("defend");
    case EUmStatusState::Discard: return TEXT("discard");
    case EUmStatusState::Choice: return TEXT("choice");
    case EUmStatusState::Sync: return TEXT("sync");
    default: return TEXT("own");
  }
}

EUmStatusState StateOf(const FS09TurnStatusInput& In, const FS09Reason& Line) {
  if (Line.Key == FName(TEXT("why.syncing"))) return EUmStatusState::Sync;
  switch (In.Mode) {
    case ES09CommandMode::CombatDefense: return EUmStatusState::Defend;
    case ES09CommandMode::DiscardDraft: return EUmStatusState::Discard;
    case ES09CommandMode::PendingChoice: return EUmStatusState::Choice;
    default: break;
  }
  // the opponent acts (their turn, the defender's answer, their choice): the verb line of SD-15
  if (Line.Key == FName(TEXT("ms.status.opp")) || Line.Key == FName(TEXT("why.wait.defender")) ||
      Line.Key == FName(TEXT("why.wait.opponent.choice"))) {
    return EUmStatusState::Opp;
  }
  return EUmStatusState::Own;
}

FText LineText(const FS09Reason& Line, const FS09TurnStatusInput& In) {
  if (!Line.IsSet()) return FText::GetEmpty();
  const FString Key = Line.Key.ToString();
  FFormatNamedArguments Args;
  for (const TPair<FString, FString>& A : Line.Args) Args.Add(A.Key, FText::FromString(A.Value));
  if (Line.Key == FName(TEXT("ms.status.opp"))) {
    // the verb of the table, not the EN text S09TurnStatus puts into the trace
    const FName Verb = S09OpponentView::VerbKey(In.OpponentVerb);
    if (!Verb.IsNone()) Args.Add(TEXT("verb"), UmText::Get(EUmTable::Ms, Verb.ToString()));
  }
  EUmTable Table = Key.StartsWith(TEXT("why.")) ? EUmTable::Why : EUmTable::Ms;
  if (!UmText::Has(Table, Key)) {
    const EUmTable Other = Table == EUmTable::Why ? EUmTable::Ms : EUmTable::Why;
    if (!UmText::Has(Other, Key)) {
      UE_LOG(LogTemp, Warning, TEXT("UMHUD status: key %s is in neither ST_Ms nor ST_Why"), *Key);
      return FText::FromString(Line.Text());
    }
    Table = Other;
  }
  return Args.Num() ? UmText::Format(Table, Key, Args) : UmText::Get(Table, Key);
}

TArray<FString> KeyHints(FName LineKey) {
  const FString K = LineKey.ToString();
  if (K == TEXT("ms.status.action")) return {TEXT("hud.key.maneuver"), TEXT("hud.key.attack"), TEXT("hud.key.scheme")};
  if (K == TEXT("ms.status.end")) return {TEXT("hud.key.end_turn")};
  if (K == TEXT("ms.status.space") || K == TEXT("ms.status.attack.go") || K == TEXT("ms.status.scheme") ||
      K == TEXT("ms.status.confirm")) {
    return {TEXT("hud.key.confirm")};
  }
  if (K == TEXT("ms.status.attack.card")) return {TEXT("hud.key.card_slot")};
  if (K == TEXT("ms.status.defend")) return {TEXT("hud.key.no_defense")};
  if (K == TEXT("ms.status.resolve")) return {TEXT("hud.key.resolve")};
  return {};
}

FString BindQuotes(const FString& Text) {
  FString Out = Text;
  bool bIn = false;
  for (TCHAR& C : Out) {
    if (C == TEXT('\x00AB')) {
      bIn = true;
    } else if (C == TEXT('\x00BB')) {
      bIn = false;
    } else if (bIn && C == TEXT(' ')) {
      C = TEXT('\x00A0');
    }
  }
  return Out;
}

int32 WrapLines(const FString& Text, float WrapSu, float SizeSu, FMeasureSu Measure, float* OutWidestSu,
                TArray<FString>* OutLines) {
  TArray<FString> Words;
  Text.ParseIntoArray(Words, TEXT(" "), true);
  TArray<FString> Lines;
  FString Cur;
  for (const FString& W : Words) {
    const FString Candidate = Cur.IsEmpty() ? W : Cur + TEXT(" ") + W;
    if (Cur.IsEmpty() || Measure(Candidate, SizeSu) <= WrapSu) {
      Cur = Candidate;
    } else {
      Lines.Add(Cur);
      Cur = W;
    }
  }
  if (!Cur.IsEmpty() || Lines.Num() == 0) Lines.Add(Cur);
  float Widest = 0.0f;
  for (const FString& L : Lines) Widest = FMath::Max(Widest, Measure(L, SizeSu));
  if (OutWidestSu) *OutWidestSu = Widest;
  if (OutLines) *OutLines = Lines;
  return Lines.Num();
}

FUmStatusFit Fit(const FString& Text, float TextRoomSu, const TArray<float>& Sizes, FMeasureSu Measure) {
  FUmStatusFit Out;
  const FString Bound = BindQuotes(Text);
  for (const float Size : Sizes) {
    float Widest = 0.0f;
    TArray<FString> Lines;
    if (WrapLines(Bound, TextRoomSu, Size, Measure, &Widest, &Lines) <= MaxLines && Widest <= TextRoomSu + 0.5f) {
      Out.Display = FString::Join(Lines, TEXT("\n"));
      Out.SizeSu = Size;
      Out.Lines = Lines.Num();
      Out.TextWidthSu = Widest;
      return Out;
    }
  }
  // still longer: the smallest size, cut to two lines with «…» (the full text goes into the tooltip)
  const float Size = Sizes.Num() ? Sizes.Last() : 16.0f;
  int32 Lo = 0;
  int32 Hi = Bound.Len();
  TArray<FString> Best;
  float BestWidest = 0.0f;
  while (Lo < Hi) {
    const int32 Mid = (Lo + Hi + 1) / 2;
    const FString Cut = Bound.Left(Mid).TrimEnd() + TEXT("\x2026");
    float Widest = 0.0f;
    TArray<FString> Lines;
    if (WrapLines(Cut, TextRoomSu, Size, Measure, &Widest, &Lines) <= MaxLines && Widest <= TextRoomSu + 0.5f) {
      Lo = Mid;
      Best = MoveTemp(Lines);
      BestWidest = Widest;
    } else {
      Hi = Mid - 1;
    }
  }
  if (Best.Num() == 0) {
    Best.Add(TEXT("\x2026"));
    BestWidest = Measure(Best[0], Size);
  }
  Out.Display = FString::Join(Best, TEXT("\n"));
  Out.SizeSu = Size;
  Out.Lines = Best.Num();
  Out.bEllipsis = true;
  Out.TextWidthSu = BestWidest;
  return Out;
}

float BodyHeightSu(const FUmStatusFit& InFit, float BaseSizeSu) {
  const float Inset = 0.5f * (MinHeightSu - PitchFactor * BaseSizeSu);
  return FMath::Max(MinHeightSu, InFit.Lines * PitchFactor * InFit.SizeSu + 2.0f * Inset);
}
}  // namespace UmHudStatus

namespace {
template <typename T>
T* UmStatusMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

template <typename T>
T* UmStatusFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmStatusRowSlot(UWidget* Widget, const FMargin& Padding) {
  if (UHorizontalBoxSlot* RowSlot = Cast<UHorizontalBoxSlot>(Widget ? Widget->Slot : nullptr)) {
    RowSlot->SetPadding(Padding);
    RowSlot->SetVerticalAlignment(VAlign_Center);
    RowSlot->SetHorizontalAlignment(HAlign_Center);
  }
}

/** The em in su of a type.* token (the theme hands out points, ВР-VS2-41). */
float UmTypeSu(const UUmHudTheme& Theme, const TCHAR* Token) { return Theme.Font(Token).Size / UmHudTheme::PointsPerSu; }
}  // namespace

UClass* UUmHudStatusLine::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmHudStatusLine::StaticClass(), WidgetBlueprintPath);
}

bool UUmHudStatusLine::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UBorder* FrameWidget = UmStatusMake<UBorder>(Tree, TEXT("Frame"));
  FrameWidget->SetBrush(FSlateNoResource());
  FrameWidget->SetPadding(FMargin(0.0f));
  FrameWidget->SetHorizontalAlignment(HAlign_Center);
  FrameWidget->SetVerticalAlignment(VAlign_Top);
  FrameWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(FrameWidget, nullptr)) return Fail(TEXT("Frame"));
  USizeBox* Sized = UmStatusMake<USizeBox>(Tree, TEXT("BodyBox"));
  Sized->SetHeightOverride(UmHudStatus::MinHeightSu);
  if (!Attach(Sized, FrameWidget)) return Fail(TEXT("BodyBox"));
  UBorder* BodyWidget = UmStatusMake<UBorder>(Tree, TEXT("Body"));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("capsule"))) BodyWidget->SetBrush(*Skin);
  BodyWidget->SetPadding(FMargin(Theme.SpaceSu(TEXT("space.m")), 0.0f));
  BodyWidget->SetHorizontalAlignment(HAlign_Center);
  BodyWidget->SetVerticalAlignment(VAlign_Center);
  BodyWidget->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(BodyWidget, Sized)) return Fail(TEXT("Body"));
  UHorizontalBox* RowWidget = UmStatusMake<UHorizontalBox>(Tree, TEXT("Row"));
  if (!Attach(RowWidget, BodyWidget)) return Fail(TEXT("Row"));
  UImage* Dot = UmStatusMake<UImage>(Tree, TEXT("PulseDot"));
  Dot->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("text.secondary")), 0.5f * UmHudStatus::DotSu,
                                      FVector2D(UmHudStatus::DotSu, UmHudStatus::DotSu)));
  Dot->SetDesiredSizeOverride(FVector2D(UmHudStatus::DotSu, UmHudStatus::DotSu));
  Dot->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Dot, RowWidget)) return Fail(TEXT("PulseDot"));
  UmStatusRowSlot(Dot, FMargin(0.0f, 0.0f, UmHudStatus::DotGapSu, 0.0f));
  UTextBlock* Text = UmStatusMake<UTextBlock>(Tree, TEXT("StatusText"));
  Text->SetFont(Theme.Font(TEXT("type.heading")));
  Text->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  Text->SetShadowOffset(FVector2D::ZeroVector);
  Text->SetJustification(ETextJustify::Center);
  if (!Attach(Text, RowWidget)) return Fail(TEXT("StatusText"));
  UmStatusRowSlot(Text, FMargin(0.0f));
  UBorder* Chip = UmStatusMake<UBorder>(Tree, TEXT("KeyChip"));
  Chip->SetBrush(FSlateNoResource());
  Chip->SetPadding(FMargin(0.0f));
  Chip->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Chip, RowWidget)) return Fail(TEXT("KeyChip"));
  UmStatusRowSlot(Chip, FMargin(UmHudStatus::DotGapSu, 0.0f, 0.0f, 0.0f));
  UHorizontalBox* KeyRow = UmStatusMake<UHorizontalBox>(Tree, TEXT("KeyRow"));
  if (!Attach(KeyRow, Chip)) return Fail(TEXT("KeyRow"));
  for (int32 I = 0; I < UmHudStatus::MaxChips; ++I) {
    USizeBox* KeyBox = UmStatusMake<USizeBox>(Tree, *FString::Printf(TEXT("KeyBox%d"), I));
    KeyBox->SetMinDesiredWidth(UmHudStatus::ChipSu);
    KeyBox->SetHeightOverride(UmHudStatus::ChipSu);
    if (!Attach(KeyBox, KeyRow)) return Fail(TEXT("KeyBox"));
    UmStatusRowSlot(KeyBox, FMargin(I == 0 ? 0.0f : UmHudStatus::ChipGapSu, 0.0f, 0.0f, 0.0f));
    UBorder* Key = UmStatusMake<UBorder>(Tree, *FString::Printf(TEXT("Key%d"), I));
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("key.chip"))) Key->SetBrush(*Skin);
    Key->SetPadding(FMargin(Theme.SpaceSu(TEXT("tag.padding.x")), 0.0f));
    Key->SetHorizontalAlignment(HAlign_Center);
    Key->SetVerticalAlignment(VAlign_Center);
    if (!Attach(Key, KeyBox)) return Fail(TEXT("Key"));
    UTextBlock* KeyText = UmStatusMake<UTextBlock>(Tree, *FString::Printf(TEXT("KeyText%d"), I));
    KeyText->SetFont(Theme.Font(TEXT("type.tag")));
    KeyText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    KeyText->SetShadowOffset(FVector2D::ZeroVector);
    if (!Attach(KeyText, Key)) return Fail(TEXT("KeyText"));
  }
  return true;
}

bool UUmHudStatusLine::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD status default tree: %s"), *Error);
    Body = UmStatusFind<UBorder>(Tree, TEXT("Body"));
    StatusText = UmStatusFind<UTextBlock>(Tree, TEXT("StatusText"));
    PulseDot = UmStatusFind<UImage>(Tree, TEXT("PulseDot"));
    KeyChip = UmStatusFind<UBorder>(Tree, TEXT("KeyChip"));
    Frame = UmStatusFind<UBorder>(Tree, TEXT("Frame"));
    BodyBox = UmStatusFind<USizeBox>(Tree, TEXT("BodyBox"));
  }
  if (bFirst) {
    KeyBoxes.Reset();
    KeyTexts.Reset();
    for (int32 I = 0; I < UmHudStatus::MaxChips; ++I) {
      KeyBoxes.Add(UmStatusFind<UWidget>(WidgetTree, *FString::Printf(TEXT("KeyBox%d"), I)));
      KeyTexts.Add(UmStatusFind<UTextBlock>(WidgetTree, *FString::Printf(TEXT("KeyText%d"), I)));
    }
    // the theme font is the default composite font (FSlateFontInfo without a font object): a WBP does not keep it
    // (the text would draw as tofu) - every load takes it from the theme again
    for (UTextBlock* Key : KeyTexts) {
      if (Key) Key->SetFont(UUmHudTheme::Get().Font(TEXT("type.tag")));
    }
    if (StatusText) StatusText->SetFont(UUmHudTheme::Get().Font(TEXT("type.heading")));
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    if (Frame) Frame->SetVisibility(ESlateVisibility::Collapsed);  // nothing until the first line
  }
  return bFirst;
}

bool UUmHudStatusLine::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Body) Missing.Add(TEXT("Body"));
  if (!StatusText) Missing.Add(TEXT("StatusText"));
  if (!PulseDot) Missing.Add(TEXT("PulseDot"));
  if (!KeyChip) Missing.Add(TEXT("KeyChip"));
  if (!Frame) Missing.Add(TEXT("Frame"));
  if (!BodyBox) Missing.Add(TEXT("BodyBox"));
  for (int32 I = 0; I < UmHudStatus::MaxChips; ++I) {
    if (!KeyBoxes.IsValidIndex(I) || !KeyBoxes[I] || !KeyTexts.IsValidIndex(I) || !KeyTexts[I]) {
      Missing.Add(FString::Printf(TEXT("Key%d"), I));
    }
  }
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

double UUmHudStatusLine::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

bool UUmHudStatusLine::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

float UUmHudStatusLine::MeasureSu(const FString& Text, float SizeSu, const TCHAR* Token) const {
  if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer()) {
    FSlateFontInfo Font = UUmHudTheme::Get().Font(Token);
    Font.Size = UmHudTheme::PointsFromSu(SizeSu);
    return static_cast<float>(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, Font).X);
  }
  return 0.5f * SizeSu * Text.Len();  // no Slate (a commandlet): a condensed-face estimate
}

void UUmHudStatusLine::ApplyModel(const FS09TurnStatusInput& In) {
  const FS09Reason NewLine = S09TurnStatus::Line(In);
  const FString NewText = UmHudStatus::LineText(NewLine, In).ToString();
  const EUmStatusState NewState = UmHudStatus::StateOf(In, NewLine);
  if (bHasModel && NewText == FullText && NewState == State && NewLine.Key == LineKey) return;
  const bool bTextChanged = !bHasModel || NewText != FullText;
  Input = In;
  Line = NewLine;
  LineKey = NewLine.Key;
  FullText = NewText;
  if (State != NewState || !bHasModel) PulseStart = Now();
  State = NewState;
  bHasModel = true;
  if (bTextChanged && !FullText.IsEmpty()) FadeStart = Now();
  Render();
}

void UUmHudStatusLine::SetFrame(const FUmStatusFrame& InFrame) {
  if (StatusFrame == InFrame) return;
  StatusFrame = InFrame;
  if (bHasModel) Render();
}

void UUmHudStatusLine::Render() {
  bShown = !FullText.IsEmpty();
  if (Frame) Frame->SetVisibility(bShown ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  if (!bShown) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bOpp = State == EUmStatusState::Opp;
  // the key chips (ВР-H09: never in the text)
  KeysShown.Reset();
  if (StatusFrame.bKeyHints) {
    for (const FString& K : UmHudStatus::KeyHints(LineKey)) {
      if (KeysShown.Num() < UmHudStatus::MaxChips) KeysShown.Add(K);
    }
  }
  for (int32 I = 0; I < KeyBoxes.Num(); ++I) {
    const bool bOn = KeysShown.IsValidIndex(I);
    if (KeyBoxes[I]) KeyBoxes[I]->SetVisibility(bOn ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    if (bOn && KeyTexts.IsValidIndex(I) && KeyTexts[I]) KeyTexts[I]->SetText(UmText::Get(EUmTable::Hud, KeysShown[I]));
  }
  if (KeyChip) KeyChip->SetVisibility(KeysShown.Num() ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (PulseDot) PulseDot->SetVisibility(bOpp ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  float Extras = bOpp ? UmHudStatus::DotSu + UmHudStatus::DotGapSu : 0.0f;
  if (KeysShown.Num()) {
    // each chip as wide as its key needs (the gallery 2026-10-06: a fixed 20 su let the row outgrow the capsule)
    const float TagSu = UmTypeSu(Theme, TEXT("type.tag"));
    const float ChipPad = 2.0f * Theme.SpaceSu(TEXT("tag.padding.x"));
    Extras += UmHudStatus::DotGapSu + (KeysShown.Num() - 1) * UmHudStatus::ChipGapSu;
    for (const FString& K : KeysShown) {
      const FString Glyph = UmText::Get(EUmTable::Hud, K).ToString();
      Extras += FMath::Max(UmHudStatus::ChipSu, FMath::CeilToFloat(MeasureSu(Glyph, TagSu, TEXT("type.tag")) + ChipPad));
    }
  }
  // ВР-VS2-46: the text room, the fit (24 -> 20 -> 16 su, two lines, then «…»), the capsule from the drawn text
  const float PadX = Theme.SpaceSu(TEXT("space.m"));
  const float Room = FMath::Max(0.0f, StatusFrame.MaxWidthSu - 2.0f * PadX - Extras);
  const float Base = UmTypeSu(Theme, TEXT("type.heading"));
  const TArray<float> Sizes = {Base, UmTypeSu(Theme, TEXT("type.button")), UmTypeSu(Theme, TEXT("type.body"))};
  FitNow = UmHudStatus::Fit(FullText, Room, Sizes,
                            [this](const FString& T, float S) { return MeasureSu(T, S); });
  const float Height = UmHudStatus::BodyHeightSu(FitNow, Base);
  const float Width = FMath::Min(StatusFrame.MaxWidthSu, FMath::CeilToFloat(FitNow.TextWidthSu) + 2.0f * PadX + Extras);
  BodySizeSu = FVector2D(Width, Height);
  if (BodyBox) {
    // the capsule takes the width its row really draws (the gallery 2026-10-06: glyph side bearings and the chip
    // texts drew ~7 su wider than the measure - a fixed width pushed the chips into the edge); the lines are broken
    // above, so the auto width never wraps; the frame's width is the cap
    BodyBox->ClearWidthOverride();
    BodyBox->SetMaxDesiredWidth(StatusFrame.MaxWidthSu);
    BodyBox->SetHeightOverride(Height);
  }
  if (Body) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("capsule"), StatusFrame.PxPerSu)) Body->SetBrush(*Skin);
    Body->SetPadding(FMargin(PadX, 0.0f));
    // «…»: the full text in the tooltip - the capsule then takes the hover
    Body->SetToolTipText(FitNow.bEllipsis ? FText::FromString(FullText) : FText::GetEmpty());
    Body->SetVisibility(FitNow.bEllipsis ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible);
  }
  if (StatusText) {
    FSlateFontInfo Font = Theme.Font(TEXT("type.heading"));
    Font.Size = UmHudTheme::PointsFromSu(FitNow.SizeSu);
    StatusText->SetFont(Font);
    StatusText->SetText(FText::FromString(FitNow.Display));
    StatusText->SetColorAndOpacity(FSlateColor(Theme.Color(bOpp ? TEXT("text.secondary") : TEXT("text.primary"))));
    // the lines are broken here (Fit): Slate draws them as given, pitch 1.25 x the size
    StatusText->SetAutoWrapText(false);
    StatusText->SetWrapTextAt(0.0f);
    float Natural = 0.0f;
    if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer()) {
      Natural = FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->GetMaxCharacterHeight(Font);
    }
    StatusText->SetLineHeightPercentage(Natural > 0.0f ? UmHudStatus::PitchFactor * FitNow.SizeSu / Natural : 1.0f);
  }
  Step();
}

float UUmHudStatusLine::GetTextOpacity() const { return StatusText ? StatusText->GetRenderOpacity() : 0.0f; }

float UUmHudStatusLine::GetDotOpacity() const { return PulseDot ? PulseDot->GetRenderOpacity() : 0.0f; }

void UUmHudStatusLine::Step() {
  const double T = Now();
  const bool bReduced = IsReduced();
  if (StatusText) {
    float Opacity = 1.0f;
    if (FadeStart >= 0.0) {
      const double Dur = bReduced ? UmHudStatus::FadeReducedMs : UmHudStatus::FadeMs;
      const float A = FMath::Clamp(static_cast<float>((T - FadeStart) * 1000.0 / Dur), 0.0f, 1.0f);
      Opacity = FMath::Lerp(UmHudStatus::FadeFrom, 1.0f, A);
      if (A >= 1.0f) FadeStart = -1.0;
    }
    if (StatusText->GetRenderOpacity() != Opacity) StatusText->SetRenderOpacity(Opacity);
  }
  if (PulseDot) {
    float Dot = 1.0f;
    if (bShown && State == EUmStatusState::Opp && !bReduced) {
      const double Phase = FMath::Fmod((T - PulseStart) * 1000.0, UmHudStatus::PulsePeriodMs) / UmHudStatus::PulsePeriodMs;
      Dot = UmHudStatus::PulseLow + (1.0f - UmHudStatus::PulseLow) * static_cast<float>(0.5 + 0.5 * FMath::Cos(2.0 * PI * Phase));
    }
    if (PulseDot->GetRenderOpacity() != Dot) PulseDot->SetRenderOpacity(Dot);
  }
}

void UUmHudStatusLine::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (FadeStart >= 0.0 || (bShown && State == EUmStatusState::Opp && !IsReduced())) Step();
}

FString UUmHudStatusLine::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudStatusLine::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& BodyRect) const {
  if (!bShown) return;
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && UmGameHudSlots::ShownByProperty(Frame);
  const bool bPainted = bVisible && !BodyRect.IsEmpty();
  TArray<FString> Keys;
  for (const FString& K : KeysShown) Keys.Add(UmText::Get(EUmTable::Hud, K).ToString().Replace(TEXT(" "), TEXT("")));
  const FString Extra = FString::Printf(TEXT("key=%s lines=%d size=%.0f ellipsis=%d keys=%s width=%.0f"),
                                        *LineKey.ToString(), FitNow.Lines, FitNow.SizeSu, FitNow.bEllipsis ? 1 : 0,
                                        Keys.Num() ? *FString::Join(Keys, TEXT(",")) : TEXT("-"), BodySizeSu.X);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-STATUS"), TEXT("umg"), UmHudStatus::StateName(State), FString(),
                                        BodyRect, bPainted, bVisible, SourceName(), Extra));
}

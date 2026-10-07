// VS-4 HB-43: ACTIONS - UUmHudActions, see UmHudActions.h.
#include "UmHudActions.h"

#include "../S08ArtHud.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformTime.h"
#include "Rendering/SlateRenderer.h"

const TCHAR* const UUmHudActions::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_ACTIONS");

namespace {
bool UmActSameButton(const FUmButtonModel& A, const FUmButtonModel& B) {
  return A.Variant == B.Variant && A.Label.EqualTo(B.Label) && A.IconName == B.IconName && A.bEnabled == B.bEnabled &&
         A.Reason.Key == B.Reason.Key && A.Reason.Args.OrderIndependentCompareEqual(B.Reason.Args) &&
         A.bSelected == B.bSelected && A.bBusy == B.bBusy && A.KeyHint.EqualTo(B.KeyHint) && A.bFocused == B.bFocused &&
         A.bDiscPrimary == B.bDiscPrimary && A.DiscSu == B.DiscSu && A.bOwnerTooltip == B.bOwnerTooltip;
}

template <typename T>
T* UmActFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

/** The HB-22 why plate of HB-42 A7: panel.bg, panel.edge 1 su, radius.s. */
FSlateBrush UmActPlate() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  return FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg")), Theme.RadiusSu(TEXT("radius.s")), Theme.Color(TEXT("panel.edge")), 1.0f);
}

/** One line of Text in the font of Token (su); a rough em estimate without a Slate renderer (headless tests). */
float UmActMeasureSu(const FString& Text, FName Token, float PxPerSu) {
  if (Text.IsEmpty()) return 0.0f;
  const FSlateFontInfo Font = UUmHudTheme::Get().Font(Token);
  const float SizeSu = Font.Size / UmHudTheme::PointsPerSu;
  if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().GetRenderer()) return 0.5f * SizeSu * Text.Len();
  const float Scale = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  const TSharedRef<FSlateFontMeasure> M = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  return static_cast<float>(M->Measure(Text, Font, Scale).X) / Scale;
}

constexpr int32 ZCell = 10;
constexpr int32 ZTip = 100;
}  // namespace

bool FUmActionsModel::operator==(const FUmActionsModel& O) const {
  if (bShow != O.bShow || State != O.State || bKeyHints != O.bKeyHints || ActionsRemaining != O.ActionsRemaining) return false;
  for (int32 I = 0; I < UmActionCount; ++I) {
    if (!UmActSameButton(Buttons[I], O.Buttons[I])) return false;
  }
  return true;
}

namespace UmHudActions {
const TCHAR* KeyName(EUmActionKey Key) {
  switch (Key) {
    case EUmActionKey::Maneuver: return TEXT("maneuver");
    case EUmActionKey::Attack: return TEXT("attack");
    case EUmActionKey::Scheme: return TEXT("scheme");
    case EUmActionKey::EndTurn: return TEXT("end");
    default: return TEXT("none");
  }
}

FName PressId(EUmActionKey Key) {
  switch (Key) {
    case EUmActionKey::Maneuver: return FName(TEXT("hud.begin.maneuver"));
    case EUmActionKey::Attack: return FName(TEXT("hud.begin.attack"));
    case EUmActionKey::Scheme: return FName(TEXT("hud.begin.scheme"));
    default: return FName(TEXT("hud.end.turn"));
  }
}

FName IconName(EUmActionKey Key) {
  switch (Key) {
    case EUmActionKey::Maneuver: return FName(TEXT("action-maneuver"));
    case EUmActionKey::Attack: return FName(TEXT("action-attack"));
    case EUmActionKey::Scheme: return FName(TEXT("action-scheme"));
    default: return FName(TEXT("action-end-turn"));
  }
}

FText Caption(EUmActionKey Key) {
  switch (Key) {
    case EUmActionKey::Maneuver: return UmText::Get(EUmTable::Hud, TEXT("hud.action.maneuver"));
    case EUmActionKey::Attack: return UmText::Get(EUmTable::Hud, TEXT("hud.action.attack"));
    case EUmActionKey::Scheme: return UmText::Get(EUmTable::Hud, TEXT("hud.action.scheme"));
    default: return UmText::Get(EUmTable::Hud, TEXT("hud.action.end_turn"));
  }
}

FText KeyLetter(EUmActionKey Key) {
  switch (Key) {
    case EUmActionKey::Maneuver: return UmText::Get(EUmTable::Hud, TEXT("hud.key.maneuver"));
    case EUmActionKey::Attack: return UmText::Get(EUmTable::Hud, TEXT("hud.key.attack"));
    case EUmActionKey::Scheme: return UmText::Get(EUmTable::Hud, TEXT("hud.key.scheme"));
    default: return UmText::Get(EUmTable::Hud, TEXT("hud.key.end_turn"));
  }
}

float CellWidthSu(EUmActionKey Key, bool bClassS) {
  if (bClassS) return CellSSu;
  return Key == EUmActionKey::EndTurn ? 86.0f : 78.0f;  // ВР-VS2-HB42-12: 3 x 78 + 86 + 3 x 8 = 344
}

FBox2D CellLocalSu(EUmActionKey Key, bool bClassS) {
  float X = 0.0f;
  for (int32 I = 0; I < static_cast<int32>(Key); ++I) X += CellWidthSu(static_cast<EUmActionKey>(I), bClassS) + GapSu;
  const float H = bClassS ? CellSSu : CellHSu;
  return FBox2D(FVector2D(X, 0.0f), FVector2D(X + CellWidthSu(Key, bClassS), H));
}

FUmActionsModel Decide(const FUmActionsInput& In) {
  FUmActionsModel M;
  M.bShow = In.bShow;
  M.bKeyHints = In.bKeyHints;
  M.ActionsRemaining = In.ActionsRemaining;
  for (int32 I = 0; I < UmActionCount; ++I) {
    const EUmActionKey Key = static_cast<EUmActionKey>(I);
    FUmButtonModel& B = M.Buttons[I];
    B.Variant = EUmButtonVariant::Disc;
    B.Label = Caption(Key);
    B.IconName = IconName(Key);
    B.KeyHint = In.bKeyHints ? KeyLetter(Key) : FText::GetEmpty();
    B.bOwnerTooltip = true;
    B.bFocused = In.FocusIndex == I;
  }
  FUmButtonModel& Mv = M.Buttons[static_cast<int32>(EUmActionKey::Maneuver)];
  FUmButtonModel& At = M.Buttons[static_cast<int32>(EUmActionKey::Attack)];
  FUmButtonModel& Sc = M.Buttons[static_cast<int32>(EUmActionKey::Scheme)];
  FUmButtonModel& End = M.Buttons[static_cast<int32>(EUmActionKey::EndTurn)];
  auto Off = [](FUmButtonModel& B, const FS09Reason& Why) {
    B.bEnabled = false;
    B.Reason = Why;
    B.bDiscPrimary = false;
  };
  // the opponent's turn: the whole row disabled with its reason (04 §2.14)
  if (!In.bViewerTurn) {
    M.State = TEXT("opp");
    for (FUmButtonModel& B : M.Buttons) Off(B, FS09Reason::Make(TEXT("why.not.your.turn")));
    return M;
  }
  const bool bManeuverDraft = In.Mode == ES09CommandMode::ManeuverDraft || In.bManeuverPending;
  M.State = bManeuverDraft                                ? TEXT("mode=maneuver")
            : In.Mode == ES09CommandMode::AttackDraft     ? TEXT("mode=attack")
            : In.Mode == ES09CommandMode::SchemeChoice    ? TEXT("mode=scheme")
                                                          : TEXT("own");
  // a command in flight: every press answers why.syncing until the server's reply (V-10)
  if (In.Busy.IsSet()) {
    for (FUmButtonModel& B : M.Buttons) Off(B, In.Busy);
    return M;
  }
  // an open maneuver draft: МАНЁВР selected, the rest wait for its confirmation (ВР-VS2-HB42-05)
  if (bManeuverDraft) {
    Mv.bSelected = true;
    const FS09Reason Draft = FS09Reason::Make(TEXT("why.draft.open"));
    Off(At, Draft);
    Off(Sc, Draft);
    Off(End, Draft);
    return M;
  }
  // the three actions: one reason for all of them when none may begin
  FS09Reason ActionWhy;
  if (In.Mode == ES09CommandMode::DiscardDraft) {
    ActionWhy = FS09Reason::Make(In.ActionsRemaining == 0 ? TEXT("why.no.actions") : TEXT("why.state.changed"));
  } else if (In.bCombat) {
    ActionWhy = FS09Reason::Make(TEXT("why.wait.defender"));
  } else if (In.BeginRefusal.IsSet()) {
    ActionWhy = In.BeginRefusal;
  } else if (In.ActionsRemaining == 0) {
    ActionWhy = FS09Reason::Make(TEXT("why.no.actions"));
  }
  if (ActionWhy.IsSet()) {
    Off(Mv, ActionWhy);
    Off(At, ActionWhy);
    Off(Sc, ActionWhy);
  } else {
    // the local drafts select their button; the other two switch the mode (ВР-VS2-HB42-05, ВР-VS4-41)
    At.bSelected = In.Mode == ES09CommandMode::AttackDraft;
    Sc.bSelected = In.Mode == ES09CommandMode::SchemeChoice;
    if (In.bNoScheme && !Sc.bSelected) Off(Sc, FS09Reason::Make(TEXT("why.scheme.none")));
  }
  // КОНЕЦ ХОДА: the primary cell only while the end of turn is open (SD-44), else an ordinary disabled cell
  if (In.EndTurn.IsSet()) {
    Off(End, In.EndTurn);
  } else {
    End.bEnabled = true;
    End.bDiscPrimary = true;
  }
  return M;
}

FText WhyText(const FS09Reason& Reason) {
  if (!Reason.IsSet()) return FText::GetEmpty();
  if (Reason.Args.Num() == 0) return UmText::Get(EUmTable::Why, Reason.Key.ToString());
  FFormatNamedArguments Args;
  for (const TPair<FString, FString>& A : Reason.Args) Args.Add(A.Key, FText::FromString(A.Value));
  return UmText::Format(EUmTable::Why, Reason.Key.ToString(), Args);
}
}  // namespace UmHudActions

// ------------------------------------------------------------------------------------------------ the widget

UClass* UUmHudActions::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudActions::StaticClass(), WidgetBlueprintPath); }

bool UUmHudActions::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UCanvasPanel* RowW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Row")));
  RowW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RowW, nullptr)) return Fail(TEXT("Row"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("Maneuver"), TEXT("Attack"), TEXT("Scheme"), TEXT("EndTurn")}) {
    UUmButton* B = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name));
    if (!Attach(B, RowW)) return Fail(Name);
  }
  UBorder* TipW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Tip")));
  TipW->SetBrush(UmActPlate());
  TipW->SetPadding(FMargin(UmHudActions::TipPadSu, 0.0f));
  TipW->SetHorizontalAlignment(HAlign_Left);
  TipW->SetVerticalAlignment(VAlign_Center);
  TipW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(TipW, RowW)) return Fail(TEXT("Tip"));
  UVerticalBox* Box = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("TipBox")));
  if (!Attach(Box, TipW)) return Fail(TEXT("TipBox"));
  UHorizontalBox* Head = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("TipHead")));
  if (!Attach(Head, Box)) return Fail(TEXT("TipHead"));
  UTextBlock* CaptionW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("TipCaption")));
  CaptionW->SetFont(Theme.Font(TEXT("type.tag")));
  CaptionW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  CaptionW->SetShadowOffset(FVector2D::ZeroVector);
  if (!Attach(CaptionW, Head)) return Fail(TEXT("TipCaption"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(CaptionW->Slot)) S->SetVerticalAlignment(VAlign_Center);
  UBorder* KeyW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("TipKey")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("key.chip"))) KeyW->SetBrush(*Skin);
  KeyW->SetHorizontalAlignment(HAlign_Center);
  KeyW->SetVerticalAlignment(VAlign_Center);
  KeyW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(KeyW, Head)) return Fail(TEXT("TipKey"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(KeyW->Slot)) {
    S->SetPadding(FMargin(UmHudActions::TipChipGapSu, 0.0f, 0.0f, 0.0f));
    S->SetVerticalAlignment(VAlign_Center);
  }
  UTextBlock* KeyTextW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("TipKeyText")));
  KeyTextW->SetFont(Theme.Font(TEXT("type.tag")));
  KeyTextW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  KeyTextW->SetShadowOffset(FVector2D::ZeroVector);
  KeyTextW->SetJustification(ETextJustify::Center);
  KeyTextW->SetMinDesiredWidth(UmButton::DiscChipSu);
  if (!Attach(KeyTextW, KeyW)) return Fail(TEXT("TipKeyText"));
  UTextBlock* TextW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("TipText")));
  TextW->SetFont(Theme.Font(TEXT("type.body")));
  TextW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  TextW->SetShadowOffset(FVector2D::ZeroVector);
  if (!Attach(TextW, Box)) return Fail(TEXT("TipText"));
  return true;
}

bool UUmHudActions::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD actions default tree: %s"), *Error);
  }
  Row = UmActFind<UCanvasPanel>(WidgetTree, TEXT("Row"));
  Maneuver = UmActFind<UUmButton>(WidgetTree, TEXT("Maneuver"));
  Attack = UmActFind<UUmButton>(WidgetTree, TEXT("Attack"));
  Scheme = UmActFind<UUmButton>(WidgetTree, TEXT("Scheme"));
  EndTurn = UmActFind<UUmButton>(WidgetTree, TEXT("EndTurn"));
  Tip = UmActFind<UBorder>(WidgetTree, TEXT("Tip"));
  TipBox = UmActFind<UVerticalBox>(WidgetTree, TEXT("TipBox"));
  TipHead = UmActFind<UHorizontalBox>(WidgetTree, TEXT("TipHead"));
  TipCaption = UmActFind<UTextBlock>(WidgetTree, TEXT("TipCaption"));
  TipKey = UmActFind<UBorder>(WidgetTree, TEXT("TipKey"));
  TipKeyText = UmActFind<UTextBlock>(WidgetTree, TEXT("TipKeyText"));
  TipText = UmActFind<UTextBlock>(WidgetTree, TEXT("TipText"));
  // a WBP keeps neither the theme brush nor the fonts of the code tree: set at run time
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Tip) {
    Tip->SetBrush(UmActPlate());
    Tip->SetVisibility(ESlateVisibility::Collapsed);
  }
  for (UTextBlock* T : {TipCaption.Get(), TipKeyText.Get()}) {
    if (!T) continue;
    T->SetFont(Theme.Font(TEXT("type.tag")));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    T->SetShadowOffset(FVector2D::ZeroVector);
  }
  if (TipText) {
    TipText->SetFont(Theme.Font(TEXT("type.body")));
    TipText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    TipText->SetShadowOffset(FVector2D::ZeroVector);
    TipText->SetAutoWrapText(false);
  }
  if (TipKey) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("key.chip"))) TipKey->SetBrush(*Skin);
  }
  if (Row) Row->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  SetVisibility(ESlateVisibility::Collapsed);  // nothing before the first model
  return bFirst;
}

bool UUmHudActions::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Row) Missing.Add(TEXT("Row"));
  if (!Maneuver) Missing.Add(TEXT("Maneuver"));
  if (!Attack) Missing.Add(TEXT("Attack"));
  if (!Scheme) Missing.Add(TEXT("Scheme"));
  if (!EndTurn) Missing.Add(TEXT("EndTurn"));
  if (!Tip) Missing.Add(TEXT("Tip"));
  if (!TipCaption) Missing.Add(TEXT("TipCaption"));
  if (!TipKey) Missing.Add(TEXT("TipKey"));
  if (!TipKeyText) Missing.Add(TEXT("TipKeyText"));
  if (!TipText) Missing.Add(TEXT("TipText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudActions::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

UUmButton* UUmHudActions::GetButton(EUmActionKey Key) const {
  switch (Key) {
    case EUmActionKey::Maneuver: return Maneuver;
    case EUmActionKey::Attack: return Attack;
    case EUmActionKey::Scheme: return Scheme;
    case EUmActionKey::EndTurn: return EndTurn;
    default: return nullptr;
  }
}

void UUmHudActions::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                             TFunction<void(const FS09HudPressOutcome&, EUmActionKey)> InOnPress) {
  TSharedPtr<TFunction<void(const FS09HudPressOutcome&, EUmActionKey)>> Press =
      MakeShared<TFunction<void(const FS09HudPressOutcome&, EUmActionKey)>>(MoveTemp(InOnPress));
  for (int32 I = 0; I < UmActionCount; ++I) {
    const EUmActionKey Key = static_cast<EUmActionKey>(I);
    if (UUmButton* B = GetButton(Key)) {
      B->SetPress(UmHudActions::PressId(Key), InArbiter, FS09OnHudPressOutcome::CreateLambda([Press, Key](const FS09HudPressOutcome& O) {
        if (*Press) (*Press)(O, Key);
      }));
    }
  }
}

void UUmHudActions::SetClockForTest(TFunction<double()> InClock) {
  Clock = InClock;
  for (int32 I = 0; I < UmActionCount; ++I) {
    if (UUmButton* B = GetButton(static_cast<EUmActionKey>(I))) B->SetClockForTest(InClock);
  }
}

double UUmHudActions::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

FBox2D UUmHudActions::CellRectSu(EUmActionKey Key) const {
  const FBox2D L = UmHudActions::CellLocalSu(Key, Frame.bClassS);
  if (!Frame.RectSu.bIsValid) return L;
  return FBox2D(Frame.RectSu.Min + L.Min, Frame.RectSu.Min + L.Max);
}

void UUmHudActions::SetFrame(const FUmActionsFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  Frame = InFrame;
  bHasFrame = true;
  Relayout();
  if (bHasModel) ApplyButtons();
  TipSignature = TEXT("#");
  StepTip();
}

void UUmHudActions::Relayout() {
  for (int32 I = 0; I < UmActionCount; ++I) {
    const EUmActionKey Key = static_cast<EUmActionKey>(I);
    UUmButton* B = GetButton(Key);
    UCanvasPanelSlot* S = B ? Cast<UCanvasPanelSlot>(B->Slot) : nullptr;
    if (!S) continue;
    const FBox2D C = UmHudActions::CellLocalSu(Key, Frame.bClassS);
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(C.Min);
    S->SetSize(C.GetSize());
    S->SetZOrder(ZCell);
  }
}

void UUmHudActions::ApplyModel(const FUmActionsModel& InModel) {
  if (bHasModel && Model == InModel) return;
  Model = InModel;
  bHasModel = true;
  ++ApplyCount;
  SetVisibility(Model.bShow ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  ApplyButtons();
  TipSignature = TEXT("#");  // re-decide the tooltip (hidden or shown) on the next step
  StepTip();
}

void UUmHudActions::ApplyButtons() {
  for (int32 I = 0; I < UmActionCount; ++I) {
    const EUmActionKey Key = static_cast<EUmActionKey>(I);
    UUmButton* B = GetButton(Key);
    if (!B) continue;
    FUmButtonModel M = Model.Buttons[I];
    if (Frame.bClassS) {
      // class S (A9): the disc 40 su in its 48 su cell, no caption and no chip on the cell - the tooltip carries both
      M.Label = FText::GetEmpty();
      M.KeyHint = FText::GetEmpty();
      M.DiscSu = UmHudActions::DiscSSu;
      M.HeightSu = UmHudActions::CellSSu;
      M.MinWidthSu = UmHudActions::CellSSu;
    } else {
      M.DiscSu = UmHudActions::DiscLSu;
      M.HeightSu = UmHudActions::CellHSu;
      M.MinWidthSu = UmHudActions::CellWidthSu(Key, false);
    }
    B->ApplyModel(M);
  }
}

void UUmHudActions::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  StepTip();
}

void UUmHudActions::SimulatePointer(int32 Index) {
  for (int32 I = 0; I < UmActionCount; ++I) {
    if (UUmButton* B = GetButton(static_cast<EUmActionKey>(I))) B->SimulateHover(I == Index);
  }
  StepTip();
}

FText UUmHudActions::GetTipText() const {
  if (TipFor == EUmActionKey::Num) return FText::GetEmpty();
  FString S;
  if (TipCaption && TipCaption->GetVisibility() != ESlateVisibility::Collapsed) S = TipCaption->GetText().ToString();
  if (TipText && TipText->GetVisibility() != ESlateVisibility::Collapsed) {
    if (!S.IsEmpty()) S += TEXT("\n");
    S += TipText->GetText().ToString();
  }
  return FText::FromString(S);
}

void UUmHudActions::StepTip() {
  if (!bHasModel) return;
  // the pointed cell (the pointer over it) and its hover time; the keyboard focus shows its tooltip at once
  int32 Over = INDEX_NONE;
  for (int32 I = 0; I < UmActionCount; ++I) {
    const UUmButton* B = GetButton(static_cast<EUmActionKey>(I));
    if (B && B->IsPointerOver()) Over = I;
  }
  if (Over != HoverIndex) {
    HoverIndex = Over;
    HoverSince = Now();
  }
  int32 Pointed = INDEX_NONE;
  if (HoverIndex != INDEX_NONE && (bTipImmediate || Now() - HoverSince >= UmHudActions::TipDelaySec)) {
    Pointed = HoverIndex;
  } else if (HoverIndex == INDEX_NONE) {
    for (int32 I = 0; I < UmActionCount; ++I) {
      if (Model.Buttons[I].bFocused) Pointed = I;
    }
  }
  if (!Model.bShow) Pointed = INDEX_NONE;
  // class L: only a disabled button explains itself (04 §3.1); class S: every pointed button shows its caption (A9)
  if (Pointed != INDEX_NONE && !Frame.bClassS && Model.Buttons[Pointed].bEnabled) Pointed = INDEX_NONE;
  ShowTip(Pointed);
}

void UUmHudActions::ShowTip(int32 Index) {
  if (!Tip) return;
  const FUmButtonModel* B = Index != INDEX_NONE ? &Model.Buttons[Index] : nullptr;
  const FText Why = B && !B->bEnabled ? UmHudActions::WhyText(B->Reason) : FText::GetEmpty();
  const FString Signature = B ? FString::Printf(TEXT("%d|%d|%s|%s|%d|%.3f"), Index, Frame.bClassS ? 1 : 0, *Why.ToString(),
                                                *B->KeyHint.ToString(), Model.bKeyHints ? 1 : 0, Frame.PxPerSu)
                              : FString();
  if (Signature == TipSignature) return;
  TipSignature = Signature;
  if (!B) {
    Tip->SetVisibility(ESlateVisibility::Collapsed);
    TipFor = EUmActionKey::Num;
    TipRect = FBox2D(ForceInit);
    return;
  }
  using namespace UmHudActions;
  const EUmActionKey Key = static_cast<EUmActionKey>(Index);
  const float MaxW = Frame.bClassS ? TipMaxSSu : TipMaxLSu;
  const float Room = MaxW - 2.0f * TipPadSu;
  const float Px = Frame.PxPerSu;
  // the caption line (class S): caps type.tag, the key chip 8 su right of it while key hints show
  const FString CaptionS = Frame.bClassS ? Caption(Key).ToString().ToUpper() : FString();
  const bool bChip = Frame.bClassS && Model.bKeyHints;
  float HeadW = UmActMeasureSu(CaptionS, TEXT("type.tag"), Px);
  if (bChip) HeadW += TipChipGapSu + UmButton::DiscChipSu;
  // the why text: word wrap at the room, never cut (A7)
  const FString WhyS = Why.ToString();
  float WhyW = 0.0f;
  int32 WhyLines = 0;
  if (!WhyS.IsEmpty()) {
    auto Measure = [Px](const FString& T, float /*SizeSu*/) { return UmActMeasureSu(T, TEXT("type.body"), Px); };
    WhyLines = FMath::Max(1, UmHudStatus::WrapLines(WhyS, Room, 16.0f, Measure, &WhyW));
  }
  const int32 Lines = (CaptionS.IsEmpty() ? 0 : 1) + WhyLines;
  // + TipSlackSu: the text block wraps at its own width, a line measured exactly would wrap at the last glyph
  const float W = FMath::Min(MaxW, FMath::CeilToFloat(FMath::Max(HeadW, WhyW)) + TipSlackSu + 2.0f * TipPadSu);
  const float H = TipLineSu + TipMoreSu * FMath::Max(0, Lines - 1);
  // bottom = the row top - 8 su; the right edge = the pointed cell's, inside the canvas side margins
  const FBox2D Cell = CellLocalSu(Key, Frame.bClassS);
  float Right = static_cast<float>(Cell.Max.X);
  if (Frame.RectSu.bIsValid && Frame.CanvasSu.X > 0.0) {
    const float MaxRight = static_cast<float>(Frame.CanvasSu.X - Frame.MarginSu - Frame.RectSu.Min.X);
    const float MinLeft = static_cast<float>(Frame.MarginSu - Frame.RectSu.Min.X);
    Right = FMath::Min(Right, MaxRight);
    Right = FMath::Max(Right, MinLeft + W);
  }
  const FVector2D Pos(Right - W, -TipGapSu - H);
  if (TipCaption) {
    TipCaption->SetText(FText::FromString(CaptionS));
    TipCaption->SetVisibility(CaptionS.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
    TipCaption->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  }
  if (TipHead) TipHead->SetVisibility(CaptionS.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  if (TipKey && TipKeyText) {
    TipKeyText->SetText(bChip ? KeyLetter(Key) : FText::GetEmpty());
    TipKeyText->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(B->bEnabled ? TEXT("text.primary") : TEXT("text.secondary"))));
    const float LineSu = UmButton::TagAscentSu(Px) * 2400.0f / 1900.0f;
    TipKey->SetPadding(FMargin(0.0f, FMath::Max(0.0f, 0.5f * (UmButton::DiscChipSu - LineSu))));
    TipKey->SetVisibility(bChip ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (TipText) {
    TipText->SetText(Why);
    TipText->SetAutoWrapText(false);
    TipText->SetWrapTextAt(Room);
    TipText->SetVisibility(WhyS.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Tip->Slot)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(FVector2D(W, H));
    S->SetZOrder(ZTip);
  }
  Tip->SetVisibility(ESlateVisibility::HitTestInvisible);
  TipFor = Key;
  const FVector2D Origin = Frame.RectSu.bIsValid ? Frame.RectSu.Min : FVector2D::ZeroVector;
  TipRect = FBox2D(Origin + Pos, Origin + Pos + FVector2D(W, H));
}

void UUmHudActions::CollectShotLines(TArray<FString>& Out) const {
  const bool bVisible = bHasModel && Model.bShow && UmGameHudSlots::ShownByProperty(this);
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  if (Frame.RectSu.bIsValid) {
    Rect = FS08ScreenRect(Frame.RectSu.Min.X * Px, Frame.RectSu.Min.Y * Px, Frame.RectSu.Max.X * Px, Frame.RectSu.Max.Y * Px);
  }
  TArray<FString> Buttons, Cells;
  bool bPrimary = false;
  for (int32 I = 0; I < UmActionCount; ++I) {
    const EUmActionKey Key = static_cast<EUmActionKey>(I);
    const FUmButtonModel& B = Model.Buttons[I];
    const UUmButton* W = GetButton(Key);
    const TCHAR* State = W ? UmButtonStateName(W->GetState()) : TEXT("none");
    const bool bPrim = B.bEnabled && B.bDiscPrimary;
    bPrimary |= bPrim;
    Buttons.Add(FString::Printf(TEXT("%s:%s%s%s"), UmHudActions::KeyName(Key), bPrim ? TEXT("primary-") : TEXT(""), State,
                                B.bEnabled ? TEXT("") : *(TEXT(":") + B.Reason.Key.ToString())));
    const FBox2D C = CellRectSu(Key);
    Cells.Add(FString::Printf(TEXT("%.0fx%.0f"), C.Max.X - C.Min.X, C.Max.Y - C.Min.Y));
  }
  FString TipField = TEXT("none");
  if (TipFor != EUmActionKey::Num && TipRect.bIsValid) {
    TipField = FString::Printf(TEXT("%s tipRect=(%.0f,%.0f,%.0f,%.0f)"), UmHudActions::KeyName(TipFor), TipRect.Min.X * Px,
                               TipRect.Min.Y * Px, TipRect.Max.X * Px, TipRect.Max.Y * Px);
  }
  const FString Extra = FString::Printf(TEXT("class=%s actions=%d primary=%s keys=%d cells=%s buttons=%s tip=%s"),
                                        Frame.bClassS ? TEXT("S") : TEXT("L"), Model.ActionsRemaining,
                                        bPrimary ? TEXT("end") : TEXT("none"), Model.bKeyHints ? 1 : 0,
                                        *FString::Join(Cells, TEXT(",")), *FString::Join(Buttons, TEXT(",")), *TipField);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-ACTIONS"), TEXT("umg"), Model.State.IsEmpty() ? TEXT("own") : *Model.State,
                                        FString(), Rect, bVisible && !Rect.IsEmpty(), bVisible, SourceName(), Extra));
}

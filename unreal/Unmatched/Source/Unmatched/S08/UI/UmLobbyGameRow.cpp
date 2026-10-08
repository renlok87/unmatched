// VS-7 SC-08: one row of the LOBBY list - see UmLobbyGameRow.h.
#include "UmLobbyGameRow.h"

#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmPortrait.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"

namespace UmLobbyRow {
FUmLobbyColumns Columns(float RowW, float CodeW, float ModeW, float BoardW, float SeatsW, float DiscsW, float JoinW) {
  FUmLobbyColumns C;
  C.JoinW = FMath::Max(JoinMinWSu, JoinW);
  C.JoinX = RowW - EndPadSu - C.JoinW;
  C.CodeX = PadSu;
  const float CodeEnd = C.CodeX + CodeW;
  const float Gap = FMath::Max(8.0f, (C.JoinX - CodeEnd - (ModeW + BoardW + SeatsW + DiscsW)) / 5.0f);
  C.ModeX = CodeEnd + Gap;
  C.BoardX = C.ModeX + ModeW + Gap;
  C.SeatsX = C.BoardX + BoardW + Gap;
  C.DiscsX = C.SeatsX + SeatsW + Gap;
  return C;
}

FString SeatsText(int32 InSeats, int32 InMax) { return FString::Printf(TEXT("%d/%d"), InSeats, InMax); }
}  // namespace UmLobbyRow

namespace {
void UmLrPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
  }
}

void UmLrText(UTextBlock* T, const TCHAR* Type) {
  if (!T) return;
  T->SetFont(UUmHudTheme::Get().Font(FName(Type)));
  T->SetShadowOffset(FVector2D::ZeroVector);
}
}  // namespace

bool UUmLobbyGameRow::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    // a SizeBox root: the row's height in the list's vertical box (a canvas has no desired size of its own)
    USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("Box")));
    Box->SetHeightOverride(UmLobbyRow::HeightSu);
    WidgetTree->RootWidget = Box;
    Cell = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Cell")));
    Cell->SetPadding(FMargin(0.0f));
    Box->SetContent(Cell);
    Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
    Cell->SetContent(Canvas);
    for (const TCHAR* Name : {TEXT("Code"), TEXT("Mode"), TEXT("Board"), TEXT("Seats"), TEXT("WhyText")}) {
      UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
      T->SetVisibility(ESlateVisibility::HitTestInvisible);
      Canvas->AddChild(T);
    }
    HeroDiscs = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("HeroDiscs")));
    HeroDiscs->SetVisibility(ESlateVisibility::HitTestInvisible);
    Canvas->AddChild(HeroDiscs);
    UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
    JoinButton = WidgetTree->ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("JoinButton")));
    Canvas->AddChild(JoinButton);
  }
  Cell = Cast<UBorder>(WidgetTree->FindWidget(FName(TEXT("Cell"))));
  Canvas = Cast<UCanvasPanel>(WidgetTree->FindWidget(FName(TEXT("Canvas"))));
  HeroDiscs = Cast<UHorizontalBox>(WidgetTree->FindWidget(FName(TEXT("HeroDiscs"))));
  JoinButton = Cast<UUmButton>(WidgetTree->FindWidget(FName(TEXT("JoinButton"))));
  Code = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Code"))));
  Mode = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Mode"))));
  Board = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Board"))));
  Seats = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Seats"))));
  WhyText = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("WhyText"))));
  UmLrText(Code, TEXT("type.heading"));
  UmLrText(Mode, TEXT("type.body"));
  UmLrText(Board, TEXT("type.body"));
  UmLrText(Seats, TEXT("type.body"));
  UmLrText(WhyText, TEXT("type.body"));
  if (WhyText) WhyText->SetJustification(ETextJustify::Right);
  if (JoinButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.Label = UmText::Get(EUmTable::Screens, TEXT("screens.lobby.row.join"));
    B.HeightSu = UmLobbyRow::JoinHSu;
    B.MinWidthSu = UmLobbyRow::JoinMinWSu;
    JoinButton->ApplyModel(B);
  }
  Restyle();
  return bFirst;
}

void UUmLobbyGameRow::SetPress(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnOutcome) {
  if (JoinButton) JoinButton->SetPress(Id, Arbiter, OnOutcome);
}

int32 UUmLobbyGameRow::GetDiscCount() const { return HeroDiscs ? HeroDiscs->GetChildrenCount() : 0; }

void UUmLobbyGameRow::ApplyModel(const FUmLobbyRowModel& InModel, float PxPerSu) {
  const bool bDiscs = !bHasModel || InModel.HeroKeys != DiscKeys;
  Model = InModel;
  bHasModel = true;
  if (Code) Code->SetText(FText::FromString(Model.Code));
  if (Mode) Mode->SetText(Model.Mode);
  if (Board) Board->SetText(FText::FromString(Model.Board));
  if (Seats) Seats->SetText(FText::FromString(UmLobbyRow::SeatsText(Model.Seats, Model.MaxSeats)));
  if (WhyText && !Model.Why.IsNone()) WhyText->SetText(UmText::Get(EUmTable::Why, Model.Why.ToString()));
  if (bDiscs && HeroDiscs && WidgetTree) {
    HeroDiscs->ClearChildren();
    KeepAlive.Reset();
    for (int32 I = 0; I < Model.HeroKeys.Num(); ++I) {
      FUmPortraitDiscSpec Spec;
      Spec.Key = Model.HeroKeys[I];
      Spec.Name = Model.HeroNames.IsValidIndex(I) ? Model.HeroNames[I] : Model.HeroKeys[I].ToString();
      Spec.ShowSu = UmLobbyRow::DiscSu;
      Spec.PxPerSu = PxPerSu;
      FUmPortraitShown Shown;
      if (UWidget* Disc = UmPortrait::MakeDisc(*WidgetTree, this, Spec, Shown, KeepAlive)) {
        if (UHorizontalBoxSlot* S = HeroDiscs->AddChildToHorizontalBox(Disc)) {
          S->SetPadding(FMargin(I == 0 ? 0.0f : UmLobbyRow::DiscGapSu, 0.0f, 0.0f, 0.0f));
          S->SetVerticalAlignment(VAlign_Center);
        }
      }
    }
    DiscKeys = Model.HeroKeys;
  }
  Restyle();
}

void UUmLobbyGameRow::ApplyColumns(const FUmLobbyColumns& C, float RowW) {
  const float H = UmLobbyRow::HeightSu;
  const float TextY = 8.0f;  // the text boxes take the inner 40 su; the type centres itself vertically
  UmLrPlace(Code, FVector2D(C.CodeX, TextY + 4.0f), FVector2D(FMath::Max(10.0f, C.ModeX - C.CodeX - 4.0f), 32.0f));
  UmLrPlace(Mode, FVector2D(C.ModeX, TextY + 9.0f), FVector2D(FMath::Max(10.0f, C.BoardX - C.ModeX - 4.0f), 24.0f));
  UmLrPlace(Board, FVector2D(C.BoardX, TextY + 9.0f), FVector2D(FMath::Max(10.0f, C.SeatsX - C.BoardX - 4.0f), 24.0f));
  UmLrPlace(Seats, FVector2D(C.SeatsX, TextY + 9.0f), FVector2D(FMath::Max(10.0f, C.DiscsX - C.SeatsX - 4.0f), 24.0f));
  UmLrPlace(HeroDiscs, FVector2D(C.DiscsX, 0.5f * (H - UmLobbyRow::DiscSu)),
            FVector2D(2.0f * UmLobbyRow::DiscSu + UmLobbyRow::DiscGapSu, UmLobbyRow::DiscSu));
  UmLrPlace(JoinButton, FVector2D(C.JoinX, 0.5f * (H - UmLobbyRow::JoinHSu)), FVector2D(C.JoinW, UmLobbyRow::JoinHSu));
  // the why text takes the button's slot, right-aligned to its right edge (wider to the left when it needs it)
  const float WhyW = FMath::Max(C.JoinW, C.JoinX + C.JoinW - C.DiscsX - 2.0f * UmLobbyRow::DiscSu - 16.0f);
  UmLrPlace(WhyText, FVector2D(C.JoinX + C.JoinW - WhyW, TextY + 9.0f), FVector2D(WhyW, 24.0f));
  if (JoinButton) {
    FUmButtonModel B = JoinButton->GetModel();
    B.MinWidthSu = C.JoinW;
    JoinButton->ApplyModel(B);
  }
  (void)RowW;
}

void UUmLobbyGameRow::SimulateHover(bool bIn) {
  bHover = bIn;
  Restyle();
}

void UUmLobbyGameRow::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  bHover = true;
  Restyle();
}

void UUmLobbyGameRow::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  bHover = false;
  Restyle();
}

void UUmLobbyGameRow::Restyle() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bAvail = Model.Why.IsNone();
  if (Cell) {
    if (bHover && bAvail) {
      // panel.bg.hover with the inset's edge (ВР-VS4-SC08-04; the hover body is a token colour, not a skin of its own)
      const FSlateRoundedBoxBrush Hover(Theme.Color(TEXT("panel.bg.hover")), 4.0f, Theme.Color(TEXT("panel.edge")), 1.0f);
      Cell->SetBrush(Hover);
    } else if (const FSlateBrush* Inset = Theme.Skin(TEXT("panel.inset"))) {
      Cell->SetBrush(*Inset);
    }
  }
  const FSlateColor Primary(Theme.Color(TEXT("text.primary")));
  const FSlateColor Secondary(Theme.Color(TEXT("text.secondary")));
  for (UTextBlock* T : {Code.Get(), Mode.Get(), Board.Get(), Seats.Get()}) {
    if (T) T->SetColorAndOpacity(bAvail ? Primary : Secondary);
  }
  if (Seats) Seats->SetVisibility(bAvail ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (WhyText) {
    WhyText->SetColorAndOpacity(Secondary);
    WhyText->SetVisibility(bAvail ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  if (JoinButton) JoinButton->SetVisibility(bAvail ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
  SetToolTipText(bAvail ? FText::GetEmpty() : UmText::Get(EUmTable::Why, Model.Why.ToString()));
}

// VS-2 HB-14: TOP - see UmHudTop.h.
#include "UmHudTop.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08TraceLog.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/TextBlock.h"

const TCHAR* const UUmHudTop::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_TOP");

namespace UmHudTop {
FText TurnText(int32 TurnCount) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("n"), FText::AsNumber(TurnCount));
  return UmText::Format(EUmTable::Hud, TEXT("hud.top.turn"), Args);
}
}  // namespace UmHudTop

namespace {
template <typename T>
T* UmTopFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmTopRowSlot(UWidget* Widget, const FMargin& Padding, bool bFill = false) {
  if (UHorizontalBoxSlot* RowSlot = Cast<UHorizontalBoxSlot>(Widget ? Widget->Slot : nullptr)) {
    RowSlot->SetPadding(Padding);
    RowSlot->SetVerticalAlignment(VAlign_Center);
    RowSlot->SetHorizontalAlignment(HAlign_Left);
    RowSlot->SetSize(FSlateChildSize(bFill ? ESlateSizeRule::Fill : ESlateSizeRule::Automatic));
  }
}
}  // namespace

UClass* UUmHudTop::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudTop::StaticClass(), WidgetBlueprintPath); }

bool UUmHudTop::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UBorder* PlateWidget = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Plate")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel"))) PlateWidget->SetBrush(*Skin);
  PlateWidget->SetPadding(FMargin(0.0f));
  PlateWidget->SetHorizontalAlignment(HAlign_Fill);
  PlateWidget->SetVerticalAlignment(VAlign_Fill);
  PlateWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(PlateWidget, nullptr)) return Fail(TEXT("Plate"));
  UHorizontalBox* RowWidget = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Row")));
  RowWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RowWidget, PlateWidget)) return Fail(TEXT("Row"));
  // the nested widgets from their WBPs when those exist (WBP_UmButton, WBP_UmConnectionBadge), else the native trees
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  UUmButton* Menu = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("MenuButton")));
  if (!Attach(Menu, RowWidget)) return Fail(TEXT("MenuButton"));
  UmTopRowSlot(Menu, FMargin(0.0f));
  UUmConnectionBadge* Badge = Tree.ConstructWidget<UUmConnectionBadge>(UUmConnectionBadge::WidgetClass(), FName(TEXT("Conn")));
  if (!Attach(Badge, RowWidget)) return Fail(TEXT("Conn"));
  UmTopRowSlot(Badge, FMargin(0.0f));
  UTextBlock* Turn = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("TurnText")));
  Turn->SetFont(Theme.Font(TEXT("type.button")));
  Turn->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  Turn->SetShadowOffset(FVector2D::ZeroVector);
  Turn->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Turn, RowWidget)) return Fail(TEXT("TurnText"));
  // CX-08: «Ход n» 8 su after the chip (two tag.padding.x steps), the free room to the right of it
  UmTopRowSlot(Turn, FMargin(2.0f * Theme.SpaceSu(TEXT("tag.padding.x")), 0.0f, 0.0f, 0.0f), true);
  UUmButton* Log = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("LogButton")));
  Log->SetVisibility(ESlateVisibility::Collapsed);  // class S only (ВР-H07)
  if (!Attach(Log, RowWidget)) return Fail(TEXT("LogButton"));
  UmTopRowSlot(Log, FMargin(0.0f));
  return true;
}

bool UUmHudTop::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD top default tree: %s"), *Error);
    Plate = UmTopFind<UBorder>(Tree, TEXT("Plate"));
    Row = UmTopFind<UHorizontalBox>(Tree, TEXT("Row"));
    MenuButton = UmTopFind<UUmButton>(Tree, TEXT("MenuButton"));
    Conn = UmTopFind<UUmConnectionBadge>(Tree, TEXT("Conn"));
    TurnText = UmTopFind<UTextBlock>(Tree, TEXT("TurnText"));
    LogButton = UmTopFind<UUmButton>(Tree, TEXT("LogButton"));
  }
  // the plate itself never takes the mouse; the two buttons and the chip do
  if (bFirst) {
    // the theme font is the default composite font (FSlateFontInfo without a font object): a WBP does not keep it
    // (the text would draw as tofu) - every load takes it from the theme again
    if (TurnText) TurnText->SetFont(UUmHudTheme::Get().Font(TEXT("type.button")));
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  }
  return bFirst;
}

bool UUmHudTop::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Plate) Missing.Add(TEXT("Plate"));
  if (!Row) Missing.Add(TEXT("Row"));
  if (!MenuButton) Missing.Add(TEXT("MenuButton"));
  if (!Conn) Missing.Add(TEXT("Conn"));
  if (!TurnText) Missing.Add(TEXT("TurnText"));
  if (!LogButton) Missing.Add(TEXT("LogButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmHudTop::ApplyButton(UUmButton* Button, const TCHAR* IconId, const TCHAR* LabelKey, float Square, bool& bOutGlyph) {
  if (!Button) return;
  const FText Word = UmText::Get(EUmTable::Hud, LabelKey);
  FUmButtonModel M;
  M.Variant = EUmButtonVariant::Normal;
  M.IconName = FName(IconId);
  M.HeightSu = Square;
  M.MinWidthSu = Square;
  M.bFlat = true;
  Button->ApplyModel(M);
  // ВР-HB08: no glyph (not in the contract or not in the pak) -> the word on the button
  bOutGlyph = Button->Icon && Button->Icon->GetIconId() == M.IconName && Button->Icon->GetLayerTexture(0, 0) != nullptr;
  if (!bOutGlyph) {
    M.IconName = NAME_None;
    M.Label = Word;
    Button->ApplyModel(M);
    if (!bMissingTraced) {
      bMissingTraced = true;
      FS08Trace::Write(FString::Printf(TEXT("ICON missing=%s block=UI-HUD-TOP fallback=%s"), IconId, LabelKey));
    }
  }
  Button->SetToolTipText(Word);
}

void UUmHudTop::ApplyModel(const FUmTopModel& InModel) {
  if (bHasModel && Model == InModel) return;
  const bool bClassChanged = !bHasModel || Model.bClassS != InModel.bClassS || Model.PxPerSu != InModel.PxPerSu;
  Model = InModel;
  bHasModel = true;
  const float Square = UmHudTop::SquareSu(Model.bClassS);
  if (bClassChanged) {
    // HB-10: the x2 plate from 150 % (DPI x UI scale)
    if (Plate) {
      if (const FSlateBrush* Skin = UUmHudTheme::Get().SkinFor(TEXT("panel"), Model.PxPerSu)) {
        Plate->SetBrush(*Skin);
      }
    }
    ApplyButton(MenuButton, UmHudTop::MenuIcon, TEXT("hud.top.menu"), Square, bMenuGlyph);
    ApplyButton(LogButton, UmHudTop::LogIcon, TEXT("hud.top.log"), Square, bLogGlyph);
    if (LogButton) LogButton->SetVisibility(Model.bClassS ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
  }
  if (Conn) Conn->ApplyState(Model.Conn, Square);
  if (TurnText) {
    if (Model.TurnCount > 0) {
      TurnText->SetText(UmHudTop::TurnText(Model.TurnCount));
      TurnText->SetVisibility(ESlateVisibility::HitTestInvisible);
    } else {
      TurnText->SetVisibility(ESlateVisibility::Hidden);  // keeps the row in place before the first snapshot
    }
  }
}

FString UUmHudTop::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudTop::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect, const FS08ScreenRect& ConnRect) const {
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && bHasModel;
  const bool bPainted = bVisible && !Rect.IsEmpty();
  const FString Extra = FString::Printf(TEXT("turn=%d class=%s menu=%s log=%d"), Model.TurnCount,
                                        Model.bClassS ? TEXT("S") : TEXT("L"), bMenuGlyph ? TEXT("glyph") : TEXT("word"),
                                        Model.bClassS ? 1 : 0);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-TOP"), TEXT("umg"), TEXT("idle"), FString(), Rect, bPainted, bVisible,
                                        SourceName(), Extra));
  if (Conn) Out.Add(Conn->ShotLine(ConnRect, Conn->SourceName()));
}

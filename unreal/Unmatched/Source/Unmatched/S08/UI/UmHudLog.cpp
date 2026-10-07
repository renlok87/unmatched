// VS-4 HB-39: the event log - see UmHudLog.h.
#include "UmHudLog.h"

#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateColorBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/ScrollBox.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Styling/SlateTypes.h"

const TCHAR* const UUmHudLog::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_LOG");

namespace UmHudLog {
int32 VisibleRows(const FUmLogFrame& Frame) { return Frame.bClassS ? 12 : (Frame.bTall ? 6 : 3); }

float FirstRowSu(const FUmLogFrame& Frame) { return !Frame.bClassS && !Frame.bTall ? 38.0f : 40.0f; }

FBox2D ListRectSu(const FBox2D& TopRectSu) {
  if (!TopRectSu.bIsValid) return FBox2D(ForceInit);
  const FVector2D Min(TopRectSu.Min.X, TopRectSu.Max.Y + 8.0);
  return FBox2D(Min, Min + ListSizeSu());
}

FText TurnText(int32 Turn) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("n"), FText::FromString(FString::FromInt(Turn)));
  return UmText::Format(EUmTable::Hud, TEXT("hud.log.turn"), Args);
}

namespace {
FText Ms(const TCHAR* Key, const TMap<FString, FString>& In) {
  FFormatNamedArguments Args;
  for (const TPair<FString, FString>& A : In) Args.Add(A.Key, FText::FromString(A.Value));
  return Args.Num() ? UmText::Format(EUmTable::Ms, Key, Args) : UmText::Get(EUmTable::Ms, Key);
}

/** ms.log.move per move (Full = all, Inline = MaxInlineMoves - 1 + «и ещё N» beyond); ms.log.stay without moves. */
void Moves(const FS09LastMovement& Trail, const FS09EventFeed::FNameOf& FighterName, const FS09EventFeed::FCellName& CellName,
           FString& Inline, FString& Full) {
  TArray<FString> Parts;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    Parts.Add(Ms(TEXT("ms.log.move"), {{TEXT("fighterName"), FighterName(Move.FighterId)},
                                       {TEXT("from"), CellName(Move.From)},
                                       {TEXT("to"), CellName(Move.Dest())}})
                  .ToString());
  }
  if (Parts.Num() == 0) {
    Inline = Full = UmText::Get(EUmTable::Ms, TEXT("ms.log.stay")).ToString();
    return;
  }
  Full = FString::Join(Parts, TEXT(", "));
  const int32 Max = FS09EventFeed::MaxInlineMoves;
  if (Parts.Num() <= Max) {
    Inline = Full;
    return;
  }
  TArray<FString> Head(Parts.GetData(), Max - 1);
  Head.Add(Ms(TEXT("ms.log.more"), {{TEXT("n"), FString::FromInt(Parts.Num() - (Max - 1))}}).ToString());
  Inline = FString::Join(Head, TEXT(", "));
}
}  // namespace

void DescribeTrail(const FS09LastMovement& Trail, const FString& CardName, const TArray<FString>& YourFighters,
                   const FS09EventFeed::FNameOf& PlayerName, const FS09EventFeed::FNameOf& FighterName,
                   const FS09EventFeed::FCellName& CellName, FText& OutText, FText& OutFull) {
  const FString Player = PlayerName(Trail.PlayerId);
  const bool bEffect = Trail.Source == TEXT("EFFECT");
  const FString Card = CardName.IsEmpty() ? FString(TEXT("?")) : CardName;
  if (bEffect && YourFighters.Num() > 0) {
    // 03 §7 п. 3: the opponent's effect moved MY fighter - one part per fighter
    TArray<FString> Parts;
    for (const FString& Id : YourFighters) {
      Parts.Add(Ms(TEXT("ms.opp.moves.yours"), {{TEXT("fighterName"), FighterName(Id)}, {TEXT("cardName"), Card}}).ToString());
    }
    OutText = OutFull = FText::FromString(FString::Join(Parts, TEXT("; ")));
    return;
  }
  FString Inline, Full;
  Moves(Trail, FighterName, CellName, Inline, Full);
  if (bEffect) {
    OutText = Ms(TEXT("ms.log.effect"), {{TEXT("player"), Player}, {TEXT("cardName"), Card}, {TEXT("moves"), Inline}});
    OutFull = Ms(TEXT("ms.log.effect"), {{TEXT("player"), Player}, {TEXT("cardName"), Card}, {TEXT("moves"), Full}});
    return;
  }
  const FString Boost = Trail.bBoost ? Ms(TEXT("ms.log.boost.part"), {{TEXT("n"), FString::FromInt(Trail.BoostValue)},
                                                                     {TEXT("cardName"), Trail.BoostName.IsEmpty() ? FString(TEXT("?")) : Trail.BoostName}})
                                           .ToString()
                                     : FString();
  OutText = Ms(TEXT("ms.log.maneuver"), {{TEXT("player"), Player}, {TEXT("boostPart"), Boost}, {TEXT("moves"), Inline}});
  OutFull = Ms(TEXT("ms.log.maneuver"), {{TEXT("player"), Player}, {TEXT("boostPart"), Boost}, {TEXT("moves"), Full}});
}
}  // namespace UmHudLog

UClass* UUmHudLog::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudLog::StaticClass(), WidgetBlueprintPath); }

bool UUmHudLog::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UBorder* PanelW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Panel")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel"))) PanelW->SetBrush(*Skin);
  PanelW->SetPadding(FMargin(0.0f));
  PanelW->SetHorizontalAlignment(HAlign_Fill);
  PanelW->SetVerticalAlignment(VAlign_Fill);
  if (!Attach(PanelW, nullptr)) return Fail(TEXT("Panel"));
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  if (!Attach(RootW, PanelW)) return Fail(TEXT("Root"));
  auto Text = [&Tree, &Theme](const TCHAR* Name, const TCHAR* Type, const TCHAR* Color) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetFont(Theme.Font(Type));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
    T->SetShadowOffset(FVector2D::ZeroVector);
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    return T;
  };
  UTextBlock* TitleW = Text(TEXT("Title"), TEXT("type.tag"), TEXT("text.secondary"));
  TitleW->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.log.title")));
  if (!Attach(TitleW, RootW)) return Fail(TEXT("Title"));
  UTextBlock* EmptyW = Text(TEXT("Empty"), TEXT("type.body"), TEXT("text.secondary"));
  EmptyW->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.log.empty")));
  if (!Attach(EmptyW, RootW)) return Fail(TEXT("Empty"));
  UScrollBox* ScrollW = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("Scroll")));
  ScrollW->SetScrollbarThickness(FVector2D(4.0, 4.0));
  ScrollW->SetScrollbarPadding(FMargin(0.0f, 0.0f, 6.0f, 0.0f));
  ScrollW->SetAlwaysShowScrollbar(false);
  if (!Attach(ScrollW, RootW)) return Fail(TEXT("Scroll"));
  UVerticalBox* LinesW = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Lines")));
  if (!Attach(LinesW, ScrollW)) return Fail(TEXT("Lines"));
  for (UWidget* W : {static_cast<UWidget*>(TitleW), static_cast<UWidget*>(EmptyW), static_cast<UWidget*>(ScrollW)}) {
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f));
      S->SetAutoSize(false);
    }
  }
  return true;
}

bool UUmHudLog::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD log default tree: %s"), *Error);
  }
  if (bFirst) {
    BindFromTree();
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    // the string tables of the UI language and the theme's composite font (a WBP keeps neither)
    if (Title) {
      Title->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.log.title")));
      Title->SetFont(Theme.Font(TEXT("type.tag")));
    }
    if (Empty) {
      Empty->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.log.empty")));
      Empty->SetFont(Theme.Font(TEXT("type.body")));
    }
    if (Scroll) {
      // the 4 su track of 02 §4: text.secondary, the thumb text.primary
      FScrollBarStyle Bar = FScrollBarStyle::GetDefault();
      const FSlateColorBrush Track(Theme.Color(TEXT("text.secondary")));
      const FSlateColorBrush Thumb(Theme.Color(TEXT("text.primary")));
      Bar.SetVerticalBackgroundImage(Track).SetVerticalTopSlotImage(Track).SetVerticalBottomSlotImage(Track);
      Bar.SetNormalThumbImage(Thumb).SetHoveredThumbImage(Thumb).SetDraggedThumbImage(Thumb);
      Scroll->SetWidgetBarStyle(Bar);
    }
    SetVisibility(ESlateVisibility::Collapsed);
  }
  return bFirst;
}

void UUmHudLog::BindFromTree() {
  UWidgetTree* Tree = WidgetTree;
  if (!Tree) return;
  Panel = Cast<UBorder>(Tree->FindWidget(FName(TEXT("Panel"))));
  Root = Cast<UCanvasPanel>(Tree->FindWidget(FName(TEXT("Root"))));
  Title = Cast<UTextBlock>(Tree->FindWidget(FName(TEXT("Title"))));
  Empty = Cast<UTextBlock>(Tree->FindWidget(FName(TEXT("Empty"))));
  Scroll = Cast<UScrollBox>(Tree->FindWidget(FName(TEXT("Scroll"))));
  Lines = Cast<UVerticalBox>(Tree->FindWidget(FName(TEXT("Lines"))));
}

bool UUmHudLog::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Lines) Missing.Add(TEXT("Lines"));
  if (!Scroll) Missing.Add(TEXT("Scroll"));
  if (!Title) Missing.Add(TEXT("Title"));
  if (!Empty) Missing.Add(TEXT("Empty"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudLog::SourceName() const { return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName(); }

void UUmHudLog::SetFrame(const FUmLogFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  const bool bSkin = !bHasFrame || Frame.PxPerSu != InFrame.PxPerSu;
  Frame = InFrame;
  bHasFrame = true;
  if (Panel && bSkin) {
    if (const FSlateBrush* Skin = UUmHudTheme::Get().SkinFor(TEXT("panel"), Frame.PxPerSu)) Panel->SetBrush(*Skin);
  }
  Relayout();
  RestyleRows();
  ApplyVisibility();
}

void UUmHudLog::Relayout() {
  const float W = static_cast<float>(Frame.SizeSu.X);
  const float First = UmHudLog::FirstRowSu(Frame);
  const float ListH = UmHudLog::RowSu * static_cast<float>(UmHudLog::VisibleRows(Frame));
  auto Place = [](UWidget* Wd, float X, float Y, float SW, float SH) {
    if (UCanvasPanelSlot* S = Wd ? Cast<UCanvasPanelSlot>(Wd->Slot) : nullptr) {
      S->SetPosition(FVector2D(X, Y));
      S->SetSize(FVector2D(SW, SH));
    }
  };
  Place(Title, UmHudLog::TurnXSu, UmHudLog::HeaderYSu, W - 2.0f * UmHudLog::TurnXSu, 22.0f);
  Place(Empty, UmHudLog::TurnXSu, First, W - 2.0f * UmHudLog::TurnXSu, UmHudLog::RowSu);
  Place(Scroll, 0.0f, First, W, ListH);
  if (Scroll) {
    // class L: the wheel scrolls the column, no track (the rows fill it); the S list shows the track on overflow
    Scroll->SetScrollBarVisibility(Frame.bClassS ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
  }
  const float TextW = FMath::Max(40.0f, W - (UmHudLog::TextXSu + UmHudLog::TurnXSu) - (Frame.bClassS ? 12.0f : 0.0f));
  for (int32 I = 0; I < RowBoxes.Num(); ++I) {
    if (RowBoxes[I]) RowBoxes[I]->SetWidthOverride(W);
    if (RowTexts.IsValidIndex(I)) Place(RowTexts[I], UmHudLog::TextXSu, 1.0f, TextW, UmHudLog::RowSu - 1.0f);
  }
}

void UUmHudLog::AddRowWidget() {
  UWidgetTree* Tree = WidgetTree;
  if (!Tree || !Lines) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* Box = Tree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
  Box->SetHeightOverride(UmHudLog::RowSu);
  Box->SetWidthOverride(static_cast<float>(Frame.SizeSu.X));
  Lines->AddChild(Box);
  UCanvasPanel* C = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
  C->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  Box->SetContent(C);
  UImage* Stripe = Tree->ConstructWidget<UImage>(UImage::StaticClass());
  Stripe->SetVisibility(ESlateVisibility::HitTestInvisible);
  C->AddChild(Stripe);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Stripe->Slot)) {
    S->SetAutoSize(false);
    S->SetPosition(FVector2D(1.0, 1.0));
    S->SetSize(FVector2D(UmHudLog::StripeSu, UmHudLog::RowSu - 2.0f));
  }
  UTextBlock* Turn = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  Turn->SetFont(Theme.Font(TEXT("type.caption")));
  Turn->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  Turn->SetShadowOffset(FVector2D::ZeroVector);
  Turn->SetVisibility(ESlateVisibility::HitTestInvisible);
  C->AddChild(Turn);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Turn->Slot)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(UmHudLog::TurnXSu, 2.0));
  }
  UTextBlock* Txt = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  Txt->SetFont(Theme.Font(TEXT("type.body")));
  Txt->SetShadowOffset(FVector2D::ZeroVector);
  Txt->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);
  Txt->SetClipping(EWidgetClipping::ClipToBounds);
  Txt->SetVisibility(ESlateVisibility::Visible);  // the hover tooltip with the full line
  C->AddChild(Txt);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Txt->Slot)) S->SetAutoSize(false);
  RowBoxes.Add(Box);
  RowStripes.Add(Stripe);
  RowTurns.Add(Turn);
  RowTexts.Add(Txt);
}

void UUmHudLog::RestyleRows() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  while (RowBoxes.Num() < Rows.Num()) AddRowWidget();
  Relayout();
  for (int32 I = 0; I < RowBoxes.Num(); ++I) {
    const bool bUsed = I < Rows.Num();
    if (RowBoxes[I]) RowBoxes[I]->SetVisibility(bUsed ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
    if (!bUsed) continue;
    const FUmLogEntry& E = Rows[I].Entry;
    if (RowStripes[I]) RowStripes[I]->SetColorAndOpacity(Theme.Color(E.TeamSlot == 1 ? TEXT("team.p2.screen") : TEXT("team.p1.screen")));
    if (RowTurns[I]) {
      RowTurns[I]->SetText(E.Turn > 0 ? UmHudLog::TurnText(E.Turn) : FText::GetEmpty());
    }
    if (RowTexts[I]) {
      RowTexts[I]->SetText(E.Text);
      RowTexts[I]->SetToolTipText(E.Full.IsEmpty() ? E.Text : E.Full);
      RowTexts[I]->SetColorAndOpacity(FSlateColor(Theme.Color(GetRowColorToken(I))));
    }
  }
  if (Empty) Empty->SetVisibility(Rows.Num() == 0 ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
}

FName UUmHudLog::GetRowColorToken(int32 I) const {
  return I == Rows.Num() - 1 ? FName(TEXT("text.primary")) : FName(TEXT("text.secondary"));
}

FLinearColor UUmHudLog::GetStripeColor(int32 I) const {
  return RowStripes.IsValidIndex(I) && RowStripes[I] ? RowStripes[I]->GetColorAndOpacity() : FLinearColor::Transparent;
}

FText UUmHudLog::GetRowText(int32 I) const { return Rows.IsValidIndex(I) ? Rows[I].Entry.Text : FText::GetEmpty(); }

FText UUmHudLog::GetRowTooltip(int32 I) const {
  return RowTexts.IsValidIndex(I) && RowTexts[I] ? RowTexts[I]->GetToolTipText() : FText::GetEmpty();
}

bool UUmHudLog::IsAtEnd() const {
  if (!Scroll) return true;
  const float End = Scroll->GetScrollOffsetOfEnd();
  return End <= 0.0f || Scroll->GetScrollOffset() >= End - 1.0f;
}

void UUmHudLog::ScrollRowsForTest(float RowsBy) {
  if (!Scroll) return;
  Scroll->SetScrollOffset(FMath::Max(0.0f, Scroll->GetScrollOffset() + RowsBy * UmHudLog::RowSu));
}

void UUmHudLog::Push(const FUmLogEntry& Entry, double NowMs) {
  // autoscroll waits while the player reads older lines
  const bool bFollow = IsAtEnd();
  FRow R;
  R.Entry = Entry;
  R.AddedMs = NowMs;
  Rows.Add(R);
  while (Rows.Num() > UmHudLog::MaxLines) Rows.RemoveAt(0);
  RestyleRows();
  if (Scroll && bFollow) Scroll->ScrollToEnd();
  // the new line fades in (icon.appear.ms)
  const int32 Last = Rows.Num() - 1;
  if (RowBoxes.IsValidIndex(Last) && RowBoxes[Last]) RowBoxes[Last]->SetRenderOpacity(Frame.bReduced ? 1.0f : 0.0f);
}

void UUmHudLog::ApplyModel(const TArray<FUmLogEntry>& Entries, double NowMs) {
  const int32 LastSeq = Rows.Num() ? Rows.Last().Entry.Seq : -1;
  for (const FUmLogEntry& E : Entries) {
    if (E.Seq > LastSeq) Push(E, NowMs);
  }
}

void UUmHudLog::SetHidden(bool bHidden, double NowMs) {
  if (bHidden == bHiddenWanted) return;
  bHiddenWanted = bHidden;
  if (bHidden) {
    HideStartMs = NowMs;
    ShowStartMs = -1.0;
  } else {
    ShowStartMs = NowMs;
    HideStartMs = -1.0;
  }
  ApplyVisibility();
}

void UUmHudLog::SetOpen(bool bInOpen) {
  if (bOpen == bInOpen) return;
  bOpen = bInOpen;
  if (bOpen && Scroll) Scroll->ScrollToEnd();
  ApplyVisibility();
}

void UUmHudLog::ApplyVisibility() {
  const bool bWanted = (!Frame.bClassS || bOpen) && (!bHiddenWanted || BlockAlpha > 0.0f);
  const ESlateVisibility V = bWanted ? ESlateVisibility::Visible : ESlateVisibility::Collapsed;
  if (GetVisibility() != V) SetVisibility(V);
  if (Frame.bClassS && bOpen && !bHiddenWanted) {
    BlockAlpha = 1.0f;
    SetRenderOpacity(1.0f);
  }
}

bool UUmHudLog::Tick(double NowMs) {
  bool bMoving = false;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Fade = Frame.bReduced ? 0.0f : Theme.Ms(TEXT("hover.ms"));
  float A = BlockAlpha;
  if (bHiddenWanted) {
    A = Fade <= 0.0f || HideStartMs < 0.0 ? 0.0f : FMath::Clamp(1.0f - static_cast<float>((NowMs - HideStartMs) / Fade), 0.0f, 1.0f);
  } else if (ShowStartMs >= 0.0) {
    A = Fade <= 0.0f ? 1.0f : FMath::Clamp(static_cast<float>((NowMs - ShowStartMs) / Fade), 0.0f, 1.0f);
    if (A >= 1.0f) ShowStartMs = -1.0;
  } else {
    A = 1.0f;
  }
  bMoving |= A != BlockAlpha;
  BlockAlpha = A;
  if (!FMath::IsNearlyEqual(GetRenderOpacity(), A, 1.0e-3f)) SetRenderOpacity(A);
  ApplyVisibility();
  // the new lines
  const float In = Frame.bReduced ? 0.0f : Theme.Ms(TEXT("icon.appear.ms"));
  for (int32 I = 0; I < Rows.Num() && I < RowBoxes.Num(); ++I) {
    USizeBox* Box = RowBoxes[I];
    if (!Box || Box->GetRenderOpacity() >= 1.0f) continue;
    const float RA = In <= 0.0f ? 1.0f : FMath::Clamp(static_cast<float>((NowMs - Rows[I].AddedMs) / In), 0.0f, 1.0f);
    Box->SetRenderOpacity(RA);
    bMoving = true;
  }
  return bMoving;
}

int32 UUmHudLog::ShownRows() const {
  if (bHiddenWanted || (Frame.bClassS && !bOpen)) return 0;
  return FMath::Min(Rows.Num(), UmHudLog::VisibleRows(Frame));
}

FReply UUmHudLog::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::LeftMouseButton && OnInspect) {
    for (int32 I = 0; I < Rows.Num() && I < RowBoxes.Num(); ++I) {
      if (RowBoxes[I] && RowBoxes[I]->GetCachedGeometry().IsUnderLocation(InMouseEvent.GetScreenSpacePosition()) &&
          !Rows[I].Entry.CardId.IsEmpty()) {
        OnInspect(Rows[I].Entry.CardId);
        return FReply::Handled();
      }
    }
  }
  return Super::NativeOnMouseButtonUp(InGeometry, InMouseEvent);
}

void UUmHudLog::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const {
  const int32 Shown = ShownRows();
  // shown: the widget itself draws (a block never framed / still collapsed writes hidden), not hidden by the combat,
  // in S only while the list is open
  const bool bVisible = bHasFrame && UmGameHudSlots::ShownByProperty(this) && !bHiddenWanted && (!Frame.bClassS || bOpen);
  const FString State = bVisible ? FString::Printf(TEXT("lines=%d"), Shown) : FString(TEXT("hidden"));
  const FString Extra = FString::Printf(TEXT("total=%d class=%s open=%d scroll=%.0f atEnd=%d"), Rows.Num(),
                                        Frame.bClassS ? TEXT("S") : TEXT("L"), bOpen ? 1 : 0, Scroll ? Scroll->GetScrollOffset() : 0.0f,
                                        IsAtEnd() ? 1 : 0);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-LOG"), TEXT("umg"), *State, FString(), Rect, bVisible && !Rect.IsEmpty(),
                                        bVisible, SourceName(), Extra));
}

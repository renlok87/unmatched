// HB-50 TURN-STRIP: the widget - see UmHudTurnStrip.h.
#include "UmHudTurnStrip.h"
#include "../S08ArtLook.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"

namespace UmHudTurnStrip {
float CompactWidthSu(bool bClassS) {
  return 2.0f * PadSu + MainNodes * NodeSu(bClassS) + (MainNodes - 1) * LinkSu(bClassS);
}
float FullWidthSu(bool bClassS) {
  // one tray of MaxSubs sub-steps: its gap, the steps and their links, the tray's own 4 su inner pad on both sides
  return CompactWidthSu(bClassS) + TrayGapSu + 8.0f + MaxSubs * SubSu(bClassS) + (MaxSubs - 1) * SubLinkSu;
}
}  // namespace UmHudTurnStrip

namespace {
using namespace UmHudTurnStrip;

FString NodeName(const TCHAR* Part, int32 I) { return FString::Printf(TEXT("%s%d"), Part, I); }

template <typename T>
T* StripFind(UWidgetTree* Tree, const FString& Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(*Name))) : nullptr;
}

void RowSlot(UWidget* W, const FMargin& Pad) {
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(W ? W->Slot : nullptr)) {
    S->SetPadding(Pad);
    S->SetVerticalAlignment(VAlign_Center);
    S->SetHorizontalAlignment(HAlign_Left);
    S->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
  }
}

void OverlaySlotAt(UWidget* W, EHorizontalAlignment H, EVerticalAlignment V) {
  if (UOverlaySlot* S = Cast<UOverlaySlot>(W ? W->Slot : nullptr)) {
    S->SetHorizontalAlignment(H);
    S->SetVerticalAlignment(V);
  }
}

FSlateBrush RingBrush(const FLinearColor& Outline, float Width, const FLinearColor& Fill) {
  FSlateBrush B;
  B.DrawAs = ESlateBrushDrawType::RoundedBox;
  B.TintColor = FSlateColor(Fill);
  B.OutlineSettings = FSlateBrushOutlineSettings(FSlateColor(Outline), Width);
  B.OutlineSettings.RoundingType = ESlateBrushRoundingType::HalfHeightRadius;
  return B;
}

FSlateBrush TrayBrush(const FLinearColor& Outline) {
  FSlateBrush B;
  B.DrawAs = ESlateBrushDrawType::RoundedBox;
  FLinearColor Inset = UUmHudTheme::Get().Color(TEXT("panel.bg.inset"));
  Inset.A = 0.5f;
  B.TintColor = FSlateColor(Inset);
  B.OutlineSettings = FSlateBrushOutlineSettings(FVector4(6.0f, 6.0f, 6.0f, 6.0f), FSlateColor(Outline), 1.0f);
  B.OutlineSettings.RoundingType = ESlateBrushRoundingType::FixedRadius;
  return B;
}

/** Node box I: SizeBox > Overlay > Ring (border), Icon, Badge. */
bool BuildNode(UWidgetTree& Tree, FS08AttachWidget& Attach, UPanelWidget* Parent, int32 I) {
  USizeBox* Box = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(*NodeName(TEXT("Node"), I)));
  Box->SetVisibility(ESlateVisibility::Visible);  // the tooltip needs the hover
  if (!Attach(Box, Parent)) return false;
  RowSlot(Box, FMargin(0.0f));
  UOverlay* Ov = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(*NodeName(TEXT("NodeO"), I)));
  if (!Attach(Ov, Box)) return false;
  UBorder* Ring = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*NodeName(TEXT("Ring"), I)));
  Ring->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Ring, Ov)) return false;
  OverlaySlotAt(Ring, HAlign_Fill, VAlign_Fill);
  US08AnimatedIconWidget* Icon =
      Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(*NodeName(TEXT("Icon"), I)));
  Icon->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Icon, Ov)) return false;
  OverlaySlotAt(Icon, HAlign_Center, VAlign_Center);
  US08AnimatedIconWidget* Badge =
      Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(*NodeName(TEXT("Badge"), I)));
  Badge->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Badge, Ov)) return false;
  OverlaySlotAt(Badge, HAlign_Right, VAlign_Bottom);
  return true;
}

bool BuildLink(UWidgetTree& Tree, FS08AttachWidget& Attach, UPanelWidget* Parent, int32 I) {
  USizeBox* Box = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(*NodeName(TEXT("LinkBox"), I)));
  Box->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Box, Parent)) return false;
  RowSlot(Box, FMargin(0.0f));
  UBorder* Line = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*NodeName(TEXT("Link"), I)));
  Line->SetVisibility(ESlateVisibility::HitTestInvisible);
  return Attach(Line, Box);
}
}  // namespace

bool UUmHudTurnStrip::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const FString& What) {
    if (OutError) *OutError = TEXT("attach failed: ") + What;
    return false;
  };
  UOverlay* RootW = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  UBorder* PlateW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Plate")));
  if (const FSlateBrush* Skin = UUmHudTheme::Get().Skin(TEXT("panel"))) PlateW->SetBrush(*Skin);
  PlateW->SetPadding(FMargin(PadSu, 0.0f));
  PlateW->SetHorizontalAlignment(HAlign_Left);
  PlateW->SetVerticalAlignment(VAlign_Center);
  PlateW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(PlateW, RootW)) return Fail(TEXT("Plate"));
  OverlaySlotAt(PlateW, HAlign_Left, VAlign_Fill);  // as wide as its nodes (the slot is the widest strip)
  UHorizontalBox* RowW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Row")));
  RowW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RowW, PlateW)) return Fail(TEXT("Row"));
  // N0, Tray0, L0, N1, Tray1, L1, N2, L2, N3
  for (int32 I = 0; I < MainNodes; ++I) {
    if (!BuildNode(Tree, Attach, RowW, I)) return Fail(NodeName(TEXT("Node"), I));
    if (I < Trays) {
      UBorder* Tray = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*NodeName(TEXT("Tray"), I)));
      Tray->SetPadding(FMargin(4.0f, 2.0f));
      Tray->SetVisibility(ESlateVisibility::Collapsed);
      if (!Attach(Tray, RowW)) return Fail(NodeName(TEXT("Tray"), I));
      RowSlot(Tray, FMargin(TrayGapSu, 0.0f, 0.0f, 0.0f));
      UHorizontalBox* TrayRow = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(*NodeName(TEXT("TrayRow"), I)));
      TrayRow->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
      if (!Attach(TrayRow, Tray)) return Fail(NodeName(TEXT("TrayRow"), I));
      for (int32 J = 0; J < MaxSubs; ++J) {
        if (!BuildNode(Tree, Attach, TrayRow, MainNodes + I * MaxSubs + J)) return Fail(TEXT("sub node"));
        if (J + 1 < MaxSubs && !BuildLink(Tree, Attach, TrayRow, (MainNodes - 1) + I * MaxSubs + J)) return Fail(TEXT("sub link"));
      }
    }
    if (I + 1 < MainNodes && !BuildLink(Tree, Attach, RowW, I)) return Fail(NodeName(TEXT("Link"), I));
  }
  return true;
}

void UUmHudTurnStrip::BindParts() {
  UWidgetTree* Tree = WidgetTree;
  Plate = StripFind<UBorder>(Tree, TEXT("Plate"));
  Row = StripFind<UHorizontalBox>(Tree, TEXT("Row"));
  const int32 NodeCount = MainNodes + Trays * MaxSubs;
  const int32 LinkCount = (MainNodes - 1) + Trays * MaxSubs;
  Boxes.SetNum(NodeCount);
  Rings.SetNum(NodeCount);
  Icons.SetNum(NodeCount);
  Badges.SetNum(NodeCount);
  for (int32 I = 0; I < NodeCount; ++I) {
    Boxes[I] = StripFind<USizeBox>(Tree, NodeName(TEXT("Node"), I));
    Rings[I] = StripFind<UBorder>(Tree, NodeName(TEXT("Ring"), I));
    Icons[I] = StripFind<US08AnimatedIconWidget>(Tree, NodeName(TEXT("Icon"), I));
    Badges[I] = StripFind<US08AnimatedIconWidget>(Tree, NodeName(TEXT("Badge"), I));
  }
  Links.SetNum(LinkCount);
  for (int32 I = 0; I < LinkCount; ++I) Links[I] = StripFind<UBorder>(Tree, NodeName(TEXT("Link"), I));
  TrayBoxes.SetNum(Trays);
  for (int32 I = 0; I < Trays; ++I) TrayBoxes[I] = StripFind<UBorder>(Tree, NodeName(TEXT("Tray"), I));
}

bool UUmHudTurnStrip::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD turnstrip default tree: %s"), *Error);
    BindParts();
  }
  if (bFirst) SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  return bFirst;
}

void UUmHudTurnStrip::StyleNode(int32 BoxIndex, const FS09StripNode& N, float Su, FName Badge) {
  USizeBox* Box = Boxes.IsValidIndex(BoxIndex) ? Boxes[BoxIndex].Get() : nullptr;
  if (!Box) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Box->SetWidthOverride(Su);
  Box->SetHeightOverride(Su);
  Box->SetVisibility(ESlateVisibility::Visible);
  Box->SetToolTipText(N.Tip.IsNone() ? FText::GetEmpty() : UmText::Get(EUmTable::Hud, N.Tip.ToString()));
  const FLinearColor Own = Theme.Color(TEXT("turn.flash.yellow"));
  const FLinearColor Opp = Theme.Color(TEXT("team.p2.screen"));
  const FLinearColor Side = (Model.bOwnTurn || N.bMine) ? Own : Opp;
  FLinearColor Dim = Theme.Color(TEXT("text.secondary"));
  Dim.A = 0.45f;
  if (UBorder* Ring = Rings[BoxIndex].Get()) {
    Ring->SetRenderOpacity(1.0f);
    switch (N.State) {
      case ES09StripState::Now: {
        FLinearColor Fill = Side;
        Fill.A = 0.22f;
        Ring->SetBrush(RingBrush(Side, 3.0f, Fill));
        Ring->SetVisibility(ESlateVisibility::HitTestInvisible);
        break;
      }
      case ES09StripState::Done: {
        FLinearColor Edge = Side;
        Edge.A = 0.55f;
        Ring->SetBrush(RingBrush(Edge, 1.0f, FLinearColor::Transparent));
        Ring->SetVisibility(ESlateVisibility::HitTestInvisible);
        break;
      }
      case ES09StripState::Next:
        Ring->SetBrush(RingBrush(Dim, 1.0f, FLinearColor::Transparent));
        Ring->SetVisibility(ESlateVisibility::HitTestInvisible);
        break;
      default: Ring->SetVisibility(ESlateVisibility::Collapsed); break;
    }
  }
  const float PxPerSu = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  if (US08AnimatedIconWidget* Icon = Icons[BoxIndex].Get()) {
    const float IconSu = Su - (Su >= 30.0f ? 8.0f : 6.0f);
    if (Icon->GetIconId() != N.Icon || !FMath::IsNearlyEqual(Icon->GetDisplaySizeSu(), IconSu)) {
      if (Icon->SetIcon(N.Icon, IconSu, S08IconMotion::ExportSizePx(IconSu, PxPerSu))) {
        Icon->SetDisplaySizeSu(IconSu);
        Icon->ShowAtRest();
      }
    }
    // next / skip: the icon greyed through text.secondary at 55 % / 25 %
    const bool bFull = N.State == ES09StripState::Now || N.State == ES09StripState::Done;
    FLinearColor Grey = Theme.Color(TEXT("text.secondary"));
    Grey.A = N.State == ES09StripState::Next ? 0.55f : 0.25f;
    Icon->SetColorAndOpacity(bFull ? FLinearColor::White : Grey);
  }
  if (US08AnimatedIconWidget* B = Badges[BoxIndex].Get()) {
    FName Want = Badge;
    if (N.bChoice) Want = FName(TEXT("state-hint"));
    if (Want.IsNone() && N.State == ES09StripState::Done) Want = FName(TEXT("ui-check"));
    if (Want.IsNone()) {
      B->SetVisibility(ESlateVisibility::Collapsed);
    } else {
      const float BadgeSu = FMath::RoundToFloat(Su * 0.42f);
      if (B->GetIconId() != Want || !FMath::IsNearlyEqual(B->GetDisplaySizeSu(), BadgeSu)) {
        if (B->SetIcon(Want, BadgeSu, S08IconMotion::ExportSizePx(BadgeSu, PxPerSu))) {
          B->SetDisplaySizeSu(BadgeSu);
          B->ShowAtRest();
        }
      }
      B->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
  }
  if (N.State == ES09StripState::Now) {
    PulseBoxes.Add(BoxIndex);
    PulseColor = Side;
  }
}

void UUmHudTurnStrip::ApplyModel(const FS09TurnStripModel& InModel, const FUmTurnStripFrame& InFrame) {
  if (bHasModel && Model == InModel && Frame == InFrame) return;
  const bool bFrameChanged = !bHasModel || !(Frame == InFrame);
  Model = InModel;
  Frame = InFrame;
  bHasModel = true;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (bFrameChanged && Plate) {
    const bool bTable = S08ArtLook::HudTable() && Theme.HasTextureSkin(TEXT("hud.table.strip"));
    if (const FSlateBrush* Skin = bTable ? Theme.SkinFor(TEXT("hud.table.strip"), Frame.PxPerSu)
                                         : Theme.SkinV2(TEXT("hud.turn.plate"), TEXT("panel"), Frame.PxPerSu)) {
      Plate->SetBrush(*Skin);
    }
  }
  SetVisibility(Model.bShow ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  if (!Model.bShow) return;
  PulseBoxes.Reset();
  PulseStart = FPlatformTime::Seconds();
  const float Su = NodeSu(Frame.bClassS);
  const float SubS = SubSu(Frame.bClassS);
  const FLinearColor Own = Theme.Color(TEXT("turn.flash.yellow"));
  const FLinearColor Opp = Theme.Color(TEXT("team.p2.screen"));
  FLinearColor Ahead = Theme.Color(TEXT("text.secondary"));
  Ahead.A = 0.35f;
  auto LinkStyle = [&](int32 I, float W, bool bDone) {
    UBorder* L = Links.IsValidIndex(I) ? Links[I].Get() : nullptr;
    if (!L) return;
    FLinearColor C = bDone ? (Model.bOwnTurn ? Own : Opp) : Ahead;
    if (bDone) C.A = 0.8f;
    L->SetBrushColor(C);
    if (USizeBox* Box = Cast<USizeBox>(L->GetParent())) {
      Box->SetWidthOverride(W);
      Box->SetHeightOverride(2.0f);
      Box->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
  };
  for (int32 I = 0; I < MainNodes; ++I) {
    if (!Model.Nodes.IsValidIndex(I)) {
      if (Boxes.IsValidIndex(I) && Boxes[I]) Boxes[I]->SetVisibility(ESlateVisibility::Collapsed);
      continue;
    }
    const bool bCompactBadge = Frame.bCompact && I == Model.SubOf;
    StyleNode(I, Model.Nodes[I], Su, bCompactBadge ? Model.StepIcon : NAME_None);
    if (I + 1 < MainNodes) LinkStyle(I, LinkSu(Frame.bClassS), Model.Nodes[I].State == ES09StripState::Done);
  }
  for (int32 T = 0; T < Trays; ++T) {
    UBorder* Tray = TrayBoxes.IsValidIndex(T) ? TrayBoxes[T].Get() : nullptr;
    const bool bShowTray = !Frame.bCompact && Model.SubOf == T && Model.Subs.Num() > 0;
    if (Tray) {
      FLinearColor Edge = Model.bOwnTurn ? Own : Opp;
      Edge.A = 0.5f;
      Tray->SetBrush(TrayBrush(Edge));
      Tray->SetVisibility(bShowTray ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
      if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(Tray->Slot)) {
        S->SetPadding(FMargin(TrayGapSu, 0.0f, 0.0f, 0.0f));
        S->SetVerticalAlignment(VAlign_Center);
      }
    }
    if (!bShowTray) continue;
    for (int32 J = 0; J < MaxSubs; ++J) {
      const int32 Box = MainNodes + T * MaxSubs + J;
      const int32 Link = (MainNodes - 1) + T * MaxSubs + J;
      if (Model.Subs.IsValidIndex(J)) {
        StyleNode(Box, Model.Subs[J], SubS, NAME_None);
      } else if (Boxes.IsValidIndex(Box) && Boxes[Box]) {
        Boxes[Box]->SetVisibility(ESlateVisibility::Collapsed);
      }
      if (J + 1 < MaxSubs) {
        if (Model.Subs.IsValidIndex(J + 1)) {
          LinkStyle(Link, SubLinkSu, Model.Subs[J].State == ES09StripState::Done);
        } else if (Links.IsValidIndex(Link) && Links[Link]) {
          if (USizeBox* LB = Cast<USizeBox>(Links[Link]->GetParent())) LB->SetVisibility(ESlateVisibility::Collapsed);
        }
      }
    }
  }
  for (int32 I = 0; I < MainNodes; ++I) {
    if (Boxes.IsValidIndex(I) && Boxes[I]) RowSlot(Boxes[I], FMargin(0.0f));
  }
}

void UUmHudTurnStrip::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (PulseBoxes.Num() == 0) return;
  float Alpha = 1.0f;
  if (!Frame.bReducedMotion) {
    const double Ms = (FPlatformTime::Seconds() - PulseStart) * 1000.0;
    Alpha = 0.55f + 0.45f * (0.5f + 0.5f * FMath::Cos(2.0 * PI * Ms / PulseMs));
  }
  for (const int32 B : PulseBoxes) {
    if (Rings.IsValidIndex(B) && Rings[B]) Rings[B]->SetRenderOpacity(Alpha);
  }
}

int32 UUmHudTurnStrip::ShownNodes() const {
  int32 N = 0;
  for (int32 I = 0; I < MainNodes && I < Boxes.Num(); ++I) {
    if (Boxes[I] && Boxes[I]->GetVisibility() != ESlateVisibility::Collapsed && GetVisibility() != ESlateVisibility::Collapsed) ++N;
  }
  return N;
}

int32 UUmHudTurnStrip::ShownSubs() const {
  int32 N = 0;
  for (int32 T = 0; T < Trays && T < TrayBoxes.Num(); ++T) {
    if (!TrayBoxes[T] || TrayBoxes[T]->GetVisibility() == ESlateVisibility::Collapsed) continue;
    for (int32 J = 0; J < MaxSubs; ++J) {
      const int32 B = MainNodes + T * MaxSubs + J;
      if (Boxes.IsValidIndex(B) && Boxes[B] && Boxes[B]->GetVisibility() != ESlateVisibility::Collapsed) ++N;
    }
  }
  return N;
}

FText UUmHudTurnStrip::NodeTip(int32 I) const {
  if (!Boxes.IsValidIndex(I) || !Boxes[I] || Boxes[I]->GetVisibility() == ESlateVisibility::Collapsed) return FText::GetEmpty();
  return Boxes[I]->GetToolTipText();
}

void UUmHudTurnStrip::CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const {
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && bHasModel && Model.bShow;
  const FString Extra = FString::Printf(TEXT("mode=%s class=%s nodes=%d subs=%d %s"), Frame.bCompact ? TEXT("compact") : TEXT("full"),
                                        Frame.bClassS ? TEXT("S") : TEXT("L"), ShownNodes(), ShownSubs(), *Model.Key());
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-TURNSTRIP"), TEXT("umg"), Model.bOwnTurn ? TEXT("own") : TEXT("opp"),
                                        FString(), Rect, bVisible && !Rect.IsEmpty(), bVisible,
                                        bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName(), Extra));
}

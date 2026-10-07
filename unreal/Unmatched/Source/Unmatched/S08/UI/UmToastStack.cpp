// VS-4 HB-40: the toast stack - see UmToastStack.h.
#include "UmToastStack.h"

#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"

const TCHAR* const UUmToastStack::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_TOAST");

UClass* UUmToastStack::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmToastStack::StaticClass(), WidgetBlueprintPath); }

bool UUmToastStack::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* Root = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
  Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(Root, nullptr)) return Fail(TEXT("Canvas"));
  US08AnimatedIconWidget* BadgeW = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("Badge")));
  BadgeW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(BadgeW, Root)) return Fail(TEXT("Badge"));
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(BadgeW->Slot)) {
    S->SetAutoSize(false);
    S->SetSize(FVector2D(UmHudFeed::BadgeSu, UmHudFeed::BadgeSu));
    S->SetZOrder(10);
  }
  return true;
}

bool UUmToastStack::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD toast stack default tree: %s"), *Error);
  }
  if (bFirst) {
    BindFromTree();
    // the root never takes the mouse; only a sticky toast's cross does
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  }
  return bFirst;
}

void UUmToastStack::BindFromTree() {
  UWidgetTree* Tree = WidgetTree;
  if (!Tree) return;
  Canvas = Cast<UCanvasPanel>(Tree->FindWidget(FName(TEXT("Canvas"))));
  Badge = Cast<US08AnimatedIconWidget>(Tree->FindWidget(FName(TEXT("Badge"))));
}

bool UUmToastStack::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Canvas) Missing.Add(TEXT("Canvas"));
  if (!Badge) Missing.Add(TEXT("Badge"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmToastStack::SourceName() const { return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName(); }

void UUmToastStack::SetFrame(const FUmToastFrame& InFrame) {
  if (Frame == InFrame) return;
  Frame = InFrame;
  // the plans follow the cap and the drawn scale of the canvas
  for (FEntry& E : Entries) {
    E.Plan = PlanOf(E.Spec);
    if (UUmToast* W = PoolAt(E.Pool)) W->ApplySpec(E.Spec, E.Plan, Frame.PxPerSu);
  }
}

void UUmToastStack::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, TFunction<void(const FS09HudPressOutcome&, FName)> InOnClose) {
  Arbiter = InArbiter;
  OnClose = MoveTemp(InOnClose);
}

float UUmToastStack::MeasureSu(const FString& Text, float SizeSu) const {
  return MeasureOverride ? MeasureOverride(Text, SizeSu) : UmToast::MeasureBodySu(Text, SizeSu, Frame.PxPerSu);
}

FUmToastPlan UUmToastStack::PlanOf(const FUmToastSpec& Spec) const {
  return UmToast::Plan(Spec, UmHudFeed::ToastCapSu(Frame.bClassS, Frame.bTall),
                       [this](const FString& T, float S) { return MeasureSu(T, S); });
}

UUmToast* UUmToastStack::PoolAt(int32 I) { return Pool.IsValidIndex(I) ? Pool[I].Get() : nullptr; }

int32 UUmToastStack::FreePool() const {
  for (int32 I = 0; I < UmToastStack::PoolSize; ++I) {
    bool bUsed = false;
    for (const FEntry& E : Entries) bUsed |= E.Pool == I;
    if (!bUsed) return I;
  }
  return INDEX_NONE;
}

int32 UUmToastStack::Push(const FUmToastSpec& Spec, double NowMs) {
  // the same toast again renews its hold (a repeated refusal is not a second toast)
  for (FEntry& E : Entries) {
    if (E.LeaveStartMs < 0.0 && E.Spec.SameAs(Spec)) {
      if (E.ShownMs >= 0.0 && !Spec.bSticky) E.HoldUntilMs = NowMs + 1000.0 * UmHudFeed::HoldSec(Spec.Kind, Spec.HoldSec);
      return E.Id;
    }
  }
  FEntry E;
  E.Id = NextId++;
  E.Spec = Spec;
  E.Plan = PlanOf(Spec);
  E.QueuedMs = NowMs;
  Entries.Add(E);
  return E.Id;
}

void UUmToastStack::Clear() {
  for (const FEntry& E : Entries) {
    if (UUmToast* W = PoolAt(E.Pool)) W->SetVisibility(ESlateVisibility::Collapsed);
  }
  Entries.Reset();
  bExternal = false;
  ExternalSize = FVector2D::ZeroVector;
  ExternalRect = FBox2D(ForceInit);
  Placed = UmHudFeed::FStackResult();
  BadgeUntilMs = 0.0;
  if (Badge) Badge->SetVisibility(ESlateVisibility::Collapsed);
}

void UUmToastStack::SetLive(bool bLive) {
  if (!bLive && !IsEmpty()) Clear();
}

bool UUmToastStack::Dismiss(FName Key, double NowMs) {
  bool bAny = false;
  for (int32 I = Entries.Num() - 1; I >= 0; --I) {
    FEntry& E = Entries[I];
    if (E.Spec.Key != Key || E.LeaveStartMs >= 0.0) continue;
    if (E.ShownMs < 0.0) {
      Entries.RemoveAt(I);  // never shown: gone
    } else {
      StartLeave(E, NowMs);
    }
    bAny = true;
  }
  return bAny;
}

bool UUmToastStack::Has(FName Key) const {
  for (const FEntry& E : Entries) {
    if (E.Spec.Key == Key && E.LeaveStartMs < 0.0) return true;
  }
  return false;
}

void UUmToastStack::SetExternal(bool bOn, const FVector2D& SizeSu, double /*NowMs*/) {
  if (bOn && !bExternal) ExternalSeq = NextId++;
  bExternal = bOn;
  ExternalSize = bOn ? SizeSu : FVector2D::ZeroVector;
  if (!bOn) ExternalRect = FBox2D(ForceInit);
}

void UUmToastStack::StartLeave(FEntry& E, double NowMs) {
  if (E.LeaveStartMs >= 0.0) return;
  E.LeaveStartMs = NowMs;
}

float UUmToastStack::AlphaOf(const FEntry& E, double NowMs) const {
  if (E.ShownMs < 0.0) return 0.0f;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (E.LeaveStartMs >= 0.0) {
    const float Out = Frame.bReduced ? 0.0f : Theme.Ms(TEXT("icon.leave.ms"));
    return Out <= 0.0f ? 0.0f : FMath::Clamp(1.0f - static_cast<float>((NowMs - E.LeaveStartMs) / Out), 0.0f, 1.0f);
  }
  const float In = Frame.bReduced ? 0.0f : Theme.Ms(TEXT("icon.appear.ms"));
  return In <= 0.0f ? 1.0f : FMath::Clamp(static_cast<float>((NowMs - E.ShownMs) / In), 0.0f, 1.0f);
}

bool UUmToastStack::Tick(double NowMs, bool bBannerShown) {
  bool bChanged = false;
  const float OutMs = Frame.bReduced ? 0.0f : UUmHudTheme::Get().Ms(TEXT("icon.leave.ms"));
  // the leaving ones finish
  for (int32 I = Entries.Num() - 1; I >= 0; --I) {
    const FEntry& E = Entries[I];
    if (E.LeaveStartMs >= 0.0 && NowMs - E.LeaveStartMs >= OutMs) {
      if (UUmToast* W = PoolAt(E.Pool)) W->SetVisibility(ESlateVisibility::Collapsed);
      Entries.RemoveAt(I);
    }
  }
  // the holds run out
  for (FEntry& E : Entries) {
    if (E.ShownMs >= 0.0 && E.LeaveStartMs < 0.0 && E.HoldUntilMs > 0.0 && NowMs >= E.HoldUntilMs) {
      StartLeave(E, NowMs);
      bChanged = true;
    }
  }
  // a queued toast shows after the banner (04 §2.12); the oldest member leaves for it beyond MaxToasts
  if (bBannerShown) {
    for (FEntry& E : Entries) E.bWaited |= E.ShownMs < 0.0;
  } else {
    for (FEntry& E : Entries) {
      if (E.ShownMs >= 0.0) continue;
      int32 Live = bExternal ? 1 : 0;
      for (const FEntry& O : Entries) Live += O.ShownMs >= 0.0 && O.LeaveStartMs < 0.0 ? 1 : 0;
      while (Live >= UmHudFeed::MaxToasts) {
        FEntry* Oldest = nullptr;
        // a sticky rule never leaves for a newer toast (its owner closes it); the placement may still hide it
        for (FEntry& O : Entries) {
          if (O.ShownMs >= 0.0 && O.LeaveStartMs < 0.0 && !O.Spec.bSticky && (!Oldest || O.Id < Oldest->Id)) Oldest = &O;
        }
        if (!Oldest) break;
        StartLeave(*Oldest, NowMs);
        --Live;
      }
      int32 PoolSlot = FreePool();
      if (PoolSlot == INDEX_NONE) {
        // three busy: the oldest leaving one finishes now
        int32 Victim = INDEX_NONE;
        for (int32 I = 0; I < Entries.Num(); ++I) {
          if (Entries[I].LeaveStartMs >= 0.0 && (Victim == INDEX_NONE || Entries[I].Id < Entries[Victim].Id)) Victim = I;
        }
        if (Victim == INDEX_NONE) continue;
        PoolSlot = Entries[Victim].Pool;
        if (UUmToast* W = PoolAt(PoolSlot)) W->SetVisibility(ESlateVisibility::Collapsed);
        Entries.RemoveAt(Victim);
        break;  // the array moved: the queued one shows next frame
      }
      while (Pool.Num() <= PoolSlot) {
        UUmToast* W = CreateWidget<UUmToast>(this, UUmToast::WidgetClass());
        Pool.Add(W);
        if (W && Canvas) {
          Canvas->AddChild(W);
          if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) {
            S->SetAutoSize(true);
            S->SetAnchors(FAnchors(0.0f, 0.0f));
          }
          const int32 Index = Pool.Num() - 1;
          TWeakObjectPtr<UUmToastStack> WeakThis(this);
          W->SetClose(FName(*FString::Printf(TEXT("hud.toast.close.%d"), Index)), Arbiter,
                      FS09OnHudPressOutcome::CreateLambda([WeakThis, Index](const FS09HudPressOutcome& O) {
                        UUmToastStack* Self = WeakThis.Get();
                        if (!Self || !Self->OnClose) return;
                        FName Key = NAME_None;
                        for (const FEntry& X : Self->Entries) {
                          if (X.Pool == Index) Key = X.Spec.Key;
                        }
                        Self->OnClose(O, Key);
                      }));
        }
      }
      E.Pool = PoolSlot;
      // it appears from its push (a sheet's clock may jump), or from the end of the banner it waited for
      E.ShownMs = E.bWaited ? NowMs : FMath::Min(E.QueuedMs, NowMs);
      E.HoldUntilMs = E.Spec.bSticky ? 0.0 : E.ShownMs + 1000.0 * UmHudFeed::HoldSec(E.Spec.Kind, E.Spec.HoldSec);
      E.bPlaced = false;
      if (UUmToast* W = PoolAt(PoolSlot)) {
        W->ApplySpec(E.Spec, E.Plan, Frame.PxPerSu);
        W->SetRenderOpacity(0.0f);
        W->SetVisibility(ESlateVisibility::Collapsed);  // drawn once placed
      }
      bChanged = true;
    }
  }
  // the badge's 350 ms
  if (BadgeUntilMs > 0.0 && NowMs >= BadgeUntilMs) {
    BadgeUntilMs = 0.0;
    if (Badge) Badge->SetVisibility(ESlateVisibility::Collapsed);
  }
  ApplyAlphas(NowMs);
  return bChanged;
}

void UUmToastStack::ApplyAlphas(double NowMs) {
  for (const FEntry& E : Entries) {
    UUmToast* W = PoolAt(E.Pool);
    if (!W) continue;
    const float A = AlphaOf(E, NowMs);
    if (!FMath::IsNearlyEqual(W->GetRenderOpacity(), A, 1.0e-3f)) W->SetRenderOpacity(A);
    const bool bShow = E.bPlaced && E.ShownMs >= 0.0 && A > 0.0f;
    const ESlateVisibility V = bShow ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed;
    if (W->GetVisibility() != V) W->SetVisibility(V);
  }
}

void UUmToastStack::Members(TArray<FUmToastMember>& Out) const {
  Out.Reset();
  struct FM {
    int32 Order;
    FUmToastMember M;
  };
  TArray<FM> All;
  for (const FEntry& E : Entries) {
    if (E.ShownMs < 0.0 || E.LeaveStartMs >= 0.0) continue;
    All.Add({E.Id, {E.Id, E.Plan.SizeSu}});
  }
  if (bExternal && ExternalSize.X > 0.0) All.Add({ExternalSeq, {UmToastStack::ExternalId, ExternalSize}});
  All.Sort([](const FM& A, const FM& B) { return A.Order < B.Order; });
  for (const FM& X : All) Out.Add(X.M);
}

void UUmToastStack::ApplyPlacement(const UmHudFeed::FStackResult& Result, const TArray<FUmToastMember>& InMembers, double NowMs) {
  Placed = Result;
  ExternalRect = FBox2D(ForceInit);
  for (int32 I = 0; I < InMembers.Num(); ++I) {
    const int32 At = Result.Shown.Find(I);
    const FUmToastMember& M = InMembers[I];
    if (M.Id == UmToastStack::ExternalId) {
      if (At != INDEX_NONE && Result.ToastRects.IsValidIndex(At)) ExternalRect = Result.ToastRects[At];
      continue;
    }
    FEntry* E = Entries.FindByPredicate([&M](const FEntry& X) { return X.Id == M.Id; });
    if (!E) continue;
    if (At == INDEX_NONE || !Result.ToastRects.IsValidIndex(At)) {
      // step 4: the older one leaves early - a sticky rule only waits hidden for room (its owner closes it)
      if (E->Spec.bSticky) {
        E->bPlaced = false;
      } else {
        StartLeave(*E, NowMs);
      }
      continue;
    }
    const FBox2D& R = Result.ToastRects[At];
    E->bPlaced = true;
    if (UUmToast* W = PoolAt(E->Pool)) {
      if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) S->SetPosition(R.Min);
    }
  }
  ApplyAlphas(NowMs);
  // the trace line of the placement (04 §2.12: TOAST place=bottom|top overlap=0)
  const FBox2D B = Result.Bounds();
  PendingPlaceLine = Result.Place == EUmFeedPlace::None
                         ? FString()
                         : FString::Printf(TEXT("TOAST place=%s step=%s overlap=%.0f n=%d kinds=%s dropped=%d y=%.0f h=%.0f sub=%d "
                                                "external=%d attempts=%d"),
                                           Result.bTop ? TEXT("top") : TEXT("bottom"), UmHudFeed::PlaceName(Result.Place),
                                           Result.OverlapPx2, Result.ToastRects.Num(), *KindsField(), Result.Dropped,
                                           B.bIsValid ? B.Min.Y : -1.0, B.bIsValid ? B.Max.Y - B.Min.Y : 0.0,
                                           Result.SubRect.bIsValid ? 1 : 0, ExternalRect.bIsValid ? 1 : 0, Result.Attempts);
}

FString UUmToastStack::TakePlaceLine() {
  if (PendingPlaceLine.IsEmpty() || PendingPlaceLine == LastPlaceLine) return FString();
  LastPlaceLine = PendingPlaceLine;
  return PendingPlaceLine;
}

void UUmToastStack::ShowBadge(const FVector2D& CentreSu, double NowMs) {
  BadgeCentreSu = CentreSu;
  BadgeUntilMs = NowMs + UUmHudTheme::Get().Ms(TEXT("refuse.ms"));
  if (!Badge) return;
  if (Badge->GetIconId() != FName(TEXT("badge-refuse"))) {
    const int32 Px = S08IconMotion::ExportSizePx(UmHudFeed::BadgeSu, Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f);
    if (Badge->SetIcon(FName(TEXT("badge-refuse")), UmHudFeed::BadgeSu, Px)) Badge->SetDisplaySizeSu(UmHudFeed::BadgeSu);
  }
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Badge->Slot)) {
    S->SetPosition(CentreSu - FVector2D(0.5f * UmHudFeed::BadgeSu, 0.5f * UmHudFeed::BadgeSu));
  }
  Badge->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (Frame.bReduced) {
    Badge->ShowAtRest();
  } else {
    Badge->PlayAnim(FName(TEXT("appear")));
  }
}

FBox2D UUmToastStack::BadgeRectSu() const {
  if (BadgeUntilMs <= 0.0) return FBox2D(ForceInit);
  const FVector2D H(0.5f * UmHudFeed::BadgeSu, 0.5f * UmHudFeed::BadgeSu);
  return FBox2D(BadgeCentreSu - H, BadgeCentreSu + H);
}

void UUmToastStack::DrawnRectsSu(TArray<FBox2D>& Out) const {
  TArray<const FEntry*> Shown;
  for (const FEntry& E : Entries) {
    if (E.bPlaced && E.ShownMs >= 0.0) Shown.Add(&E);
  }
  Shown.Sort([](const FEntry& A, const FEntry& B) { return A.Id < B.Id; });
  for (const FEntry* E : Shown) {
    const UUmToast* W = Pool.IsValidIndex(E->Pool) ? Pool[E->Pool].Get() : nullptr;
    const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
    if (!S) continue;
    const FVector2D P = S->GetPosition();
    Out.Add(FBox2D(P, P + E->Plan.SizeSu));
  }
}

bool UUmToastStack::HitsClose(const FVector2D& PointSu) const {
  for (const FEntry& E : Entries) {
    if (!E.bPlaced || E.ShownMs < 0.0 || E.LeaveStartMs >= 0.0 || !E.Plan.bClose) continue;
    const UUmToast* W = Pool.IsValidIndex(E.Pool) ? Pool[E.Pool].Get() : nullptr;
    const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
    if (!S) continue;
    // the whole toast: a click a little off the cross must not reach the board either
    const FBox2D R(S->GetPosition(), S->GetPosition() + E.Plan.SizeSu);
    if (R.IsInside(PointSu)) return true;
  }
  return false;
}

int32 UUmToastStack::NumShown() const {
  int32 N = 0;
  for (const FEntry& E : Entries) N += E.bPlaced && E.ShownMs >= 0.0 && E.LeaveStartMs < 0.0 ? 1 : 0;
  return N;
}

FString UUmToastStack::KindsField() const {
  TArray<const FEntry*> Shown;
  for (const FEntry& E : Entries) {
    if (E.ShownMs >= 0.0 && E.LeaveStartMs < 0.0) Shown.Add(&E);
  }
  Shown.Sort([](const FEntry& A, const FEntry& B) { return A.Id < B.Id; });
  TArray<FString> Out;
  for (const FEntry* E : Shown) Out.Add(UmHudFeed::KindName(E->Spec.Kind));
  if (bExternal) Out.Add(TEXT("pending"));
  return Out.Num() ? FString::Join(Out, TEXT(",")) : FString(TEXT("-"));
}

void UUmToastStack::CollectShotLines(TArray<FString>& Out) const {
  TArray<FBox2D> Rects;
  DrawnRectsSu(Rects);
  if (ExternalRect.bIsValid) Rects.Add(ExternalRect);
  if (Rects.Num() == 0 && BadgeUntilMs <= 0.0) return;
  FBox2D B(ForceInit);
  for (const FBox2D& R : Rects) B += R;
  if (!B.bIsValid) B = BadgeRectSu();
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  Rect.X0 = static_cast<float>(B.Min.X) * Px;
  Rect.Y0 = static_cast<float>(B.Min.Y) * Px;
  Rect.X1 = static_cast<float>(B.Max.X) * Px;
  Rect.Y1 = static_cast<float>(B.Max.Y) * Px;
  bool bSticky = false;
  for (const FEntry& E : Entries) bSticky |= E.Spec.bSticky && E.ShownMs >= 0.0 && E.LeaveStartMs < 0.0;
  const FString Extra = FString::Printf(TEXT("n=%d kinds=%s step=%s overlap=%.0f dropped=%d sticky=%d external=%d badge=%d class=%s"),
                                        Rects.Num(), *KindsField(), UmHudFeed::PlaceName(Placed.Place), Placed.OverlapPx2,
                                        Placed.Dropped, bSticky ? 1 : 0, ExternalRect.bIsValid ? 1 : 0, BadgeUntilMs > 0.0 ? 1 : 0,
                                        Frame.bClassS ? TEXT("S") : TEXT("L"));
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-TOAST"), TEXT("umg"), Placed.bTop ? TEXT("top") : TEXT("bottom"), FString(), Rect,
                                        !Rect.IsEmpty(), true, SourceName(), Extra));
}

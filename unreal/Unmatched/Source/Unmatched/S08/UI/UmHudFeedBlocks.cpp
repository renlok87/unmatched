// VS-4 HB-39...HB-41: the game mode's side of the feed blocks - see UmHudFeedBlocks.h.
#include "UmHudFeedBlocks.h"

#include "UmGameHud.h"
#include "Components/CanvasPanelSlot.h"

TArray<FString> FUmFeedBlocks::Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                                     const TSharedPtr<FS09HudPressArbiter>& Arbiter, FCallbacks Callbacks) {
  TArray<FString> Lines;
  if (Blocks.IsSlate(FName(TEXT("log")))) {
    Lines.Add(TEXT("HUD-FEED-UMG log=slate reason=-S08SlateHud=log"));
  } else {
    UUmHudLog* L = CreateWidget<UUmHudLog>(&Game, UUmHudLog::WidgetClass());
    if (L && Game.SetBlock(EUmGameSlot::Log, L)) {
      L->SetOnInspect(MoveTemp(Callbacks.OnLogInspect));
      Log = L;
      FString Missing;
      Lines.Add(FString::Printf(TEXT("HUD-FEED-UMG log=umg created=1 source=%s parts=%d missing=%s"), *L->SourceName(),
                                L->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
    } else {
      Lines.Add(TEXT("HUD-FEED-UMG log=umg created=0 reason=create-failed"));
    }
  }
  if (Blocks.IsSlate(FName(TEXT("toast")))) {
    Lines.Add(TEXT("HUD-FEED-UMG toast=slate reason=-S08SlateHud=toast"));
  } else {
    UUmToastStack* T = CreateWidget<UUmToastStack>(&Game, UUmToastStack::WidgetClass());
    if (T && Game.SetBlock(EUmGameSlot::Toast, T)) {
      T->SetInput(Arbiter, MoveTemp(Callbacks.OnToastClose));
      Toasts = T;
      FString Missing;
      Lines.Add(FString::Printf(TEXT("HUD-FEED-UMG toast=umg created=1 source=%s parts=%d missing=%s toastSource=%s"), *T->SourceName(),
                                T->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing,
                                *UUmToast::WidgetClass()->GetPathName()));
    } else {
      Lines.Add(TEXT("HUD-FEED-UMG toast=umg created=0 reason=create-failed"));
    }
  }
  if (Blocks.IsSlate(FName(TEXT("sub")))) {
    Lines.Add(TEXT("HUD-FEED-UMG sub=slate reason=-S08SlateHud=sub"));
  } else {
    UUmHudSubtitle* S = CreateWidget<UUmHudSubtitle>(&Game, UUmHudSubtitle::WidgetClass());
    if (S && Game.SetBlock(EUmGameSlot::Sub, S)) {
      Sub = S;
      FString Missing;
      Lines.Add(FString::Printf(TEXT("HUD-FEED-UMG sub=umg created=1 source=%s parts=%d missing=%s"), *S->SourceName(),
                                S->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
    } else {
      Lines.Add(TEXT("HUD-FEED-UMG sub=umg created=0 reason=create-failed"));
    }
  }
  return Lines;
}

UmHudFeed::FStackInput FUmFeedBlocks::StackInput(const FUmFeedInput& In, const TArray<FUmToastMember>& Members,
                                                 const FVector2D& SubSize) {
  using namespace UmHudFeed;
  FStackInput S;
  const FUmHudLayout& L = *In.Layout;
  S.CanvasSu = L.CanvasSu;
  S.PxPerSu = L.PxPerSu;
  S.MarginSu = L.MarginSu;
  for (const FUmToastMember& M : Members) S.Toasts.Add(M.SizeSu);
  S.Sub = SubSize;
  S.ToastCentreXSu = 0.5f * static_cast<float>(L.CanvasSu.X);
  S.SubCentreXSu = L.HandRightSu > L.HandLeftSu ? 0.5f * (L.HandLeftSu + L.HandRightSu) : S.ToastCentreXSu;
  S.TopBandSu = L.bClassS ? TopBandSSu : TopBandLSu;
  const FBox2D& Top = L.Rect(EUmHudBlock::Top);
  const float StatusBottom = In.StatusBottomSu >= 0.0f ? In.StatusBottomSu
                             : L.Rect(EUmHudBlock::Status).bIsValid ? static_cast<float>(L.Rect(EUmHudBlock::Status).Max.Y)
                             : Top.bIsValid ? static_cast<float>(Top.Max.Y)
                                            : L.MarginSu;
  S.MinTopSu = StatusBottom + GapSu;
  // step 1: over the hand caption (at rest) or over the lowered hand; the capsule 4 su over the cards
  const FBox2D& CaptionRow = L.Rect(EUmHudBlock::HandCaption);
  const float CardsTop = In.CardsTopSu >= 0.0f ? In.CardsTopSu
                         : CaptionRow.bIsValid ? static_cast<float>(CaptionRow.Max.Y)
                                               : static_cast<float>(L.CanvasSu.Y) - L.MarginSu;
  const float CaptionTop = In.CaptionSu.bIsValid ? static_cast<float>(In.CaptionSu.Min.Y) : CardsTop;
  S.ToastBottomSu = CaptionTop - GapSu;
  S.SubBottomSu = CardsTop - SubOverCardsSu;
  S.Obstacles = In.Figures;
  if (!In.bCombat) S.Obstacles.Append(In.Spaces);  // ВР-VS2-HB38-18: in the defense window the spaces are not obstacles
  S.Obstacles.Append(In.Blocks);
  if (In.CaptionSu.bIsValid) {
    // the «Рука n/max» plate keeps 8 su from the toasts and the capsule on every side (HB-38: HAND-CAPTION-gap)
    S.Obstacles.Add(In.CaptionSu.ExpandBy(CaptionGapSu));
  }
  return S;
}

namespace {
uint32 UmFeedHash(const UmHudFeed::FStackInput& S) {
  const float Px = S.PxPerSu > 0.0f ? S.PxPerSu : 1.0f;
  auto Q = [Px](double V) { return static_cast<uint32>(static_cast<int32>(FMath::RoundToDouble(V * Px * 2.0))); };
  uint32 H = HashCombine(Q(S.CanvasSu.X), Q(S.CanvasSu.Y));
  H = HashCombine(H, Q(S.Sub.X));
  H = HashCombine(H, Q(S.Sub.Y));
  H = HashCombine(H, Q(S.ToastBottomSu));
  H = HashCombine(H, Q(S.SubBottomSu));
  H = HashCombine(H, Q(S.MinTopSu));
  H = HashCombine(H, Q(S.TopBandSu));
  for (const FVector2D& T : S.Toasts) H = HashCombine(H, HashCombine(Q(T.X), Q(T.Y)));
  for (const FBox2D& O : S.Obstacles) {
    if (!O.bIsValid) continue;
    H = HashCombine(H, HashCombine(HashCombine(Q(O.Min.X), Q(O.Min.Y)), HashCombine(Q(O.Max.X), Q(O.Max.Y))));
  }
  return H;
}
}  // namespace

TArray<FString> FUmFeedBlocks::Refresh(const FUmFeedInput& In) {
  TArray<FString> Lines;
  if (!In.Layout) return Lines;
  const FUmHudLayout& L = *In.Layout;
  // ---- the log ----
  if (UUmHudLog* LogW = Log.Get()) {
    FUmLogFrame F;
    F.bClassS = L.bClassS;
    F.bTall = L.bTall;
    F.PxPerSu = L.PxPerSu;
    F.bReduced = In.bReduced;
    F.SizeSu = L.bClassS ? UmHudLog::ListSizeSu() : (L.Rect(EUmHudBlock::Log).bIsValid ? L.Rect(EUmHudBlock::Log).GetSize() : FVector2D(300.0, 200.0));
    LogW->SetFrame(F);
    if ((In.bCombat || !In.bLive) && LogW->IsOpen()) LogW->SetOpen(false);
    LogW->SetHidden(In.bCombat || !In.bLive, In.NowMs);
    LogW->Tick(In.NowMs);
    const FString Line = FString::Printf(TEXT("HUD-LOG shown=%d total=%d hidden=%d open=%d class=%s"), LogW->ShownRows(), LogW->Num(),
                                         LogW->IsHiddenByCombat() ? 1 : 0, LogW->IsOpen() ? 1 : 0, L.bClassS ? TEXT("S") : TEXT("L"));
    if (Line != LastLogLine) {
      LastLogLine = Line;
      Lines.Add(Line);
    }
    LogRect = L.bClassS ? UmHudLog::ListRectSu(L.Rect(EUmHudBlock::Top)) : L.Rect(EUmHudBlock::Log);
  }
  // ---- the clocks ----
  bool bChanged = false;
  UUmToastStack* T = Toasts.Get();
  if (T) {
    FUmToastFrame F;
    F.CanvasSu = L.CanvasSu;
    F.PxPerSu = L.PxPerSu;
    F.bClassS = L.bClassS;
    F.bTall = L.bTall;
    F.bReduced = In.bReduced;
    T->SetFrame(F);
    T->SetLive(In.bLive);  // VS-4 HB-49: no toast survives into the lobby / result / interruption screen
    T->SetExternal(In.PendingToastSu.X > 0.0 && In.PendingToastSu.Y > 0.0, In.PendingToastSu, In.NowMs);
    bChanged |= T->Tick(In.NowMs, In.bBannerShown);
  }
  UUmHudSubtitle* S = Sub.Get();
  if (S) {
    S->SetPxPerSu(L.PxPerSu, In.bReduced);
    bChanged |= S->Tick(In.NowMs);
  }
  // ---- the group ----
  TArray<FUmToastMember> Members;
  if (T) T->Members(Members);
  const FVector2D SubSize = S ? S->DesiredSizeSu() : FVector2D::ZeroVector;
  const UmHudFeed::FStackInput SI = StackInput(In, Members, SubSize);
  uint32 Hash = UmFeedHash(SI);
  for (const FUmToastMember& M : Members) Hash = HashCombine(Hash, static_cast<uint32>(M.Id + 7));
  if (bChanged || !bHasHash || Hash != PlaceHash) {
    PlaceHash = Hash;
    bHasHash = true;
    Placed = UmHudFeed::Place(SI);
    if (T) {
      T->ApplyPlacement(Placed, Members, In.NowMs);
      const FString PlaceLine = T->TakePlaceLine();
      if (!PlaceLine.IsEmpty()) Lines.Add(PlaceLine);
    }
    if (S) S->ApplyPlacement(Placed.SubRect, In.bHandLowered);
  }
  return Lines;
}

void FUmFeedBlocks::PushLog(const FUmLogEntry& Entry, double NowMs) {
  if (UUmHudLog* L = Log.Get()) L->Push(Entry, NowMs);
}

void FUmFeedBlocks::PushToast(const FUmToastSpec& Spec, double NowMs) {
  if (UUmToastStack* T = Toasts.Get()) T->Push(Spec, NowMs);
}

void FUmFeedBlocks::DismissToast(FName Key, double NowMs) {
  if (UUmToastStack* T = Toasts.Get()) T->Dismiss(Key, NowMs);
}

bool FUmFeedBlocks::ShowBadge(const FVector2D& CentreSu, double NowMs, float SizeSu) {
  if (UUmToastStack* T = Toasts.Get()) return T->ShowBadge(CentreSu, NowMs, SizeSu);
  return false;
}

void FUmFeedBlocks::ShowSubtitle(const FUmSubtitleModel& Model) {
  if (UUmHudSubtitle* S = Sub.Get()) S->ApplyModel(Model);
  bHasHash = false;  // place again
}

void FUmFeedBlocks::HideSubtitle() {
  if (UUmHudSubtitle* S = Sub.Get()) S->Hide();
  bHasHash = false;
}

void FUmFeedBlocks::SetLogOpen(bool bOpen) {
  // class S only has the list (the press of «Журнал»); in class L the flag changes nothing
  if (UUmHudLog* L = Log.Get()) L->SetOpen(bOpen);
}

bool FUmFeedBlocks::IsLogOpen() const { return Log.IsValid() && Log->IsOpen(); }

FBox2D FUmFeedBlocks::PendingToastRect() const { return Toasts.IsValid() ? Toasts->GetExternalRect() : FBox2D(ForceInit); }

FBox2D FUmFeedBlocks::LogListRectSu() const { return IsLogOpen() ? LogRect : FBox2D(ForceInit); }

bool FUmFeedBlocks::CoversPoint(const FVector2D& PointSu) const {
  const FBox2D List = LogListRectSu();
  if (List.bIsValid && List.IsInside(PointSu)) return true;
  return Toasts.IsValid() && Toasts->HitsClose(PointSu);
}

void FUmFeedBlocks::CollectShotLines(TArray<FString>& Out, float PxPerSu) const {
  const float Px = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  if (const UUmHudLog* L = Log.Get()) {
    FS08ScreenRect Rect;
    if (LogRect.bIsValid) {
      Rect.X0 = static_cast<float>(LogRect.Min.X) * Px;
      Rect.Y0 = static_cast<float>(LogRect.Min.Y) * Px;
      Rect.X1 = static_cast<float>(LogRect.Max.X) * Px;
      Rect.Y1 = static_cast<float>(LogRect.Max.Y) * Px;
    }
    L->CollectShotLines(Out, Rect);
  }
  if (const UUmToastStack* T = Toasts.Get()) T->CollectShotLines(Out);
  if (const UUmHudSubtitle* S = Sub.Get()) S->CollectShotLines(Out);
}

// VS-4 HB-40 / HB-41: the toast and subtitle rules - see UmHudFeed.h.
#include "UmHudFeed.h"

#include "UmText.h"

namespace UmHudFeed {
EUmToastKind KindOfKey(FName Key) {
  const FString K = Key.ToString();
  if (K.StartsWith(TEXT("why."))) return EUmToastKind::Error;
  if (K.StartsWith(TEXT("ms.hint."))) return EUmToastKind::Warning;
  return EUmToastKind::Info;
}

const TCHAR* KindName(EUmToastKind Kind) {
  switch (Kind) {
    case EUmToastKind::Warning: return TEXT("warning");
    case EUmToastKind::Error: return TEXT("error");
    default: return TEXT("info");
  }
}

const TCHAR* PlaceName(EUmFeedPlace Place) {
  switch (Place) {
    case EUmFeedPlace::Bottom: return TEXT("bottom");
    case EUmFeedPlace::Top: return TEXT("top");
    case EUmFeedPlace::Upward: return TEXT("upward");
    case EUmFeedPlace::Newest: return TEXT("newest");
    case EUmFeedPlace::Fail: return TEXT("fail");
    default: return TEXT("none");
  }
}

float ToastCapSu(bool bClassS, bool bTall) { return bClassS ? 440.0f : (bTall ? 560.0f : 520.0f); }

float HoldSec(EUmToastKind Kind, float RequestedSec) {
  if (Kind == EUmToastKind::Error) return 4.0f;
  return FMath::Clamp(RequestedSec > 0.0f ? RequestedSec : 3.0f, 2.0f, 4.0f);
}

FText ReasonText(const FS09Reason& Reason) {
  if (!Reason.IsSet()) return FText::GetEmpty();
  const FString Key = Reason.Key.ToString();
  EUmTable Table = Key.StartsWith(TEXT("why.")) ? EUmTable::Why : Key.StartsWith(TEXT("hud.")) ? EUmTable::Hud : EUmTable::Ms;
  if (!UmText::Has(Table, Key)) {
    for (const EUmTable Other : {EUmTable::Why, EUmTable::Ms, EUmTable::Hud}) {
      if (UmText::Has(Other, Key)) {
        Table = Other;
        break;
      }
    }
  }
  FFormatNamedArguments Args;
  for (const TPair<FString, FString>& A : Reason.Args) Args.Add(A.Key, FText::FromString(A.Value));
  FText Out = Args.Num() ? UmText::Format(Table, Key, Args) : UmText::Get(Table, Key);
  if (Reason.Args.Contains(TEXT("orderHint"))) {
    // MS-E-34 (FS09Reason::Text): the ally leaves later in the order - say how to fix it
    Out = FText::Format(FText::FromString(TEXT("{0}. {1}")), Out, UmText::Get(EUmTable::Ms, TEXT("ms.order.swap.hint")));
  }
  const FString* Cell = Reason.Args.Find(TEXT("cell"));
  if (Cell && !Cell->IsEmpty()) Out = FText::Format(FText::FromString(TEXT("{0}: {1}")), FText::FromString(*Cell), Out);
  return Out;
}

float ToastHeightSu(int32 Lines) {
  return Lines <= 1 ? ToastMinHSu : FMath::Max(ToastMinHSu, 16.0f + ToastLinePitchSu * static_cast<float>(Lines - 1) + 24.0f);
}

double OverlapPx2(const FBox2D& R, const TArray<FBox2D>& Obstacles, float PxPerSu) {
  if (!R.bIsValid) return 0.0;
  double Sum = 0.0;
  for (const FBox2D& O : Obstacles) {
    if (!O.bIsValid) continue;
    const double W = FMath::Min(R.Max.X, O.Max.X) - FMath::Max(R.Min.X, O.Min.X);
    const double H = FMath::Min(R.Max.Y, O.Max.Y) - FMath::Max(R.Min.Y, O.Min.Y);
    if (W > 0.0 && H > 0.0) Sum += W * H;
  }
  return Sum * PxPerSu * PxPerSu;
}

FBox2D FStackResult::Bounds() const {
  FBox2D Out(ForceInit);
  for (const FBox2D& R : ToastRects) Out += R;
  if (SubRect.bIsValid) Out += SubRect;
  return Out;
}

namespace {
/** The group's rects with its top at Top (bTopAnchor) or its bottom at the step-1 anchors. Members = indices of the
 *  toasts in it; offsets are relative to the group top. */
struct FGroup {
  TArray<int32> Members;
  TArray<FBox2D> Toasts;
  FBox2D Sub = FBox2D(ForceInit);
  float Height = 0.0f;
};

float CentreX(const FStackInput& In, float Asked, float W) {
  const float CW = static_cast<float>(In.CanvasSu.X);
  const float C = Asked >= 0.0f ? Asked : 0.5f * CW;
  // inside the canvas margins
  return FMath::Clamp(C - 0.5f * W, In.MarginSu, FMath::Max(In.MarginSu, CW - In.MarginSu - W));
}

FGroup Layout(const FStackInput& In, const TArray<int32>& Members, float Top) {
  FGroup G;
  G.Members = Members;
  float Y = Top;
  for (int32 I = 0; I < Members.Num(); ++I) {
    const FVector2D S = In.Toasts[Members[I]];
    const float X = CentreX(In, In.ToastCentreXSu, static_cast<float>(S.X));
    G.Toasts.Add(FBox2D(FVector2D(X, Y), FVector2D(X + S.X, Y + S.Y)));
    Y += static_cast<float>(S.Y) + GapSu;
  }
  if (In.Sub.X > 0.0 && In.Sub.Y > 0.0) {
    if (Members.Num() == 0) Y = Top;
    const float X = CentreX(In, In.SubCentreXSu, static_cast<float>(In.Sub.X));
    G.Sub = FBox2D(FVector2D(X, Y), FVector2D(X + In.Sub.X, Y + In.Sub.Y));
    Y += static_cast<float>(In.Sub.Y);
  } else if (Members.Num() > 0) {
    Y -= GapSu;
  }
  G.Height = Y - Top;
  return G;
}

/** Step 1: the group's top so that the capsule's bottom (or the stack's bottom without one) sits at its anchor. */
float BottomTop(const FStackInput& In, const TArray<int32>& Members) {
  const FGroup G = Layout(In, Members, 0.0f);
  const bool bSub = In.Sub.X > 0.0 && In.Sub.Y > 0.0;
  return bSub ? In.SubBottomSu - G.Height : In.ToastBottomSu - G.Height;
}

double GroupOverlap(const FStackInput& In, const FGroup& G) {
  double Sum = 0.0;
  for (const FBox2D& R : G.Toasts) Sum += OverlapPx2(R, In.Obstacles, In.PxPerSu);
  if (G.Sub.bIsValid) Sum += OverlapPx2(G.Sub, In.Obstacles, In.PxPerSu);
  return Sum;
}

/** The highest top a crossing pair allows: the member's bottom on the obstacle's top. */
float ClearTop(const FStackInput& In, const FGroup& G, float Top) {
  float Best = Top;
  auto Check = [&In, &Best, Top](const FBox2D& R) {
    if (!R.bIsValid) return;
    for (const FBox2D& O : In.Obstacles) {
      if (!O.bIsValid) continue;
      const double W = FMath::Min(R.Max.X, O.Max.X) - FMath::Max(R.Min.X, O.Min.X);
      const double H = FMath::Min(R.Max.Y, O.Max.Y) - FMath::Max(R.Min.Y, O.Min.Y);
      if (W <= 0.0 || H <= 0.0) continue;
      const float Need = Top - static_cast<float>(R.Max.Y - O.Min.Y);
      Best = FMath::Min(Best, Need);
    }
  };
  for (const FBox2D& R : G.Toasts) Check(R);
  Check(G.Sub);
  return Best;
}

struct FTry {
  FGroup G;
  double Overlap = 0.0;
  EUmFeedPlace Place = EUmFeedPlace::None;
};

/** Steps 1-3 for one member set; true with Out at the first 0 px^2 position. Every position goes to Best (the least
 *  overlap) for step 5. */
bool Chain(const FStackInput& In, const TArray<int32>& Members, FTry& Out, FTry& Best, int32& Attempts) {
  auto Consider = [&Best](const FTry& T) {
    if (Best.Place == EUmFeedPlace::None || T.Overlap < Best.Overlap) Best = T;
  };
  // 1: over the hand
  {
    FTry T;
    T.G = Layout(In, Members, BottomTop(In, Members));
    T.Overlap = GroupOverlap(In, T.G);
    T.Place = EUmFeedPlace::Bottom;
    ++Attempts;
    Consider(T);
    if (T.Overlap <= 0.0) {
      Out = T;
      return true;
    }
  }
  // 2: the top band
  const float Px = In.PxPerSu > 0.0f ? In.PxPerSu : 1.0f;
  float Top = In.TopBandSu;
  FTry T;
  T.G = Layout(In, Members, Top);
  T.Overlap = GroupOverlap(In, T.G);
  T.Place = EUmFeedPlace::Top;
  ++Attempts;
  Consider(T);
  if (T.Overlap <= 0.0 && Top >= In.MinTopSu - 1.0e-3f) {
    Out = T;
    return true;
  }
  // 3: up by whole pixels from the band - each jump puts the lowest crossing member's bottom on its obstacle's top,
  // snapped up to the pixel grid (the smallest shift: any free top lies at or above every such bound)
  for (int32 Guard = 0; Guard < 64; ++Guard) {
    const float Clear = ClearTop(In, T.G, Top);
    const float ShiftPx = FMath::CeilToFloat((In.TopBandSu - Clear) * Px - 1.0e-3f);
    const float Next = In.TopBandSu - FMath::Max(ShiftPx, 1.0f) / Px;
    if (Next >= Top - 1.0e-4f) break;  // no progress
    Top = Next;
    if (Top < In.MinTopSu - 1.0e-3f) break;
    T.G = Layout(In, Members, Top);
    T.Overlap = GroupOverlap(In, T.G);
    T.Place = EUmFeedPlace::Upward;
    ++Attempts;
    Consider(T);
    if (T.Overlap <= 0.0) {
      Out = T;
      return true;
    }
  }
  return false;
}
}  // namespace

FStackResult Place(const FStackInput& In) {
  FStackResult R;
  const bool bSub = In.Sub.X > 0.0 && In.Sub.Y > 0.0;
  if (In.Toasts.Num() == 0 && !bSub) return R;
  // at most MaxToasts: the newest ones
  TArray<int32> All;
  for (int32 I = FMath::Max(0, In.Toasts.Num() - MaxToasts); I < In.Toasts.Num(); ++I) All.Add(I);
  R.Dropped = In.Toasts.Num() - All.Num();
  FTry Found, Best;
  bool bOk = Chain(In, All, Found, Best, R.Attempts);
  if (!bOk && All.Num() > 1) {
    // 4: only the newest (the older leaves early)
    const TArray<int32> Newest = {All.Last()};
    bOk = Chain(In, Newest, Found, Best, R.Attempts);
    if (bOk) {
      R.Dropped += All.Num() - 1;
      Found.Place = EUmFeedPlace::Newest;
    }
  }
  const FTry& Use = bOk ? Found : Best;
  R.Place = bOk ? Use.Place : EUmFeedPlace::Fail;
  R.OverlapPx2 = bOk ? 0.0 : Use.Overlap;
  if (!bOk) R.Dropped = In.Toasts.Num() - Use.G.Members.Num();
  R.Shown = Use.G.Members;
  R.ToastRects = Use.G.Toasts;
  R.SubRect = Use.G.Sub;
  // «top» for the gate: the group sits in the upper half of the canvas
  const FBox2D B = R.Bounds();
  R.bTop = B.bIsValid && B.Min.Y < 0.5 * In.CanvasSu.Y;
  return R;
}
}  // namespace UmHudFeed

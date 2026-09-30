#include "S08ArtHud.h"

#include "Misc/ConfigCacheIni.h"
#include "Misc/Parse.h"

// ---------------------------------------------------------------- camera zoom

void FS08CameraZoomConfig::Sanitize() {
  auto Clamp = [this](float& Value, float Lo, float Hi, const TCHAR* Name) {
    if (!FMath::IsFinite(Value) || Value < Lo || Value > Hi) {
      const float Fixed = FMath::IsFinite(Value) ? FMath::Clamp(Value, Lo, Hi) : Lo;
      Issues.Add(FString::Printf(TEXT("%s=%.3f clamped to %.3f"), Name, Value, Fixed));
      Value = Fixed;
    }
  };
  Clamp(MinDistanceUU, 50.0f, 100000.0f, TEXT("minDist"));
  Clamp(OverviewOutRatio, 0.1f, 1.0f, TEXT("outRatio"));
  Clamp(WheelStepFactor, 1.01f, 3.0f, TEXT("step"));
  Clamp(ZoomAnimSeconds, MinAnimSeconds, MaxAnimSeconds, TEXT("animSeconds"));
  Clamp(OverviewReturnSeconds, 0.1f, 1.0f, TEXT("returnSeconds"));
  Clamp(FollowFromZoom, 1.0f, 20.0f, TEXT("followFrom"));
}

void FS08CameraZoomConfig::ApplyIni(const FString& IniFile) {
  if (!GConfig || IniFile.IsEmpty()) return;
  const TCHAR* Section = TEXT("Unmatched.Camera");
  bool bAny = false;
  float Value = 0.0f;
  if (GConfig->GetFloat(Section, TEXT("MinDistanceUU"), Value, IniFile)) { MinDistanceUU = Value; bAny = true; }
  if (GConfig->GetFloat(Section, TEXT("OverviewOutRatio"), Value, IniFile)) { OverviewOutRatio = Value; bAny = true; }
  if (GConfig->GetFloat(Section, TEXT("WheelStepFactor"), Value, IniFile)) { WheelStepFactor = Value; bAny = true; }
  if (GConfig->GetFloat(Section, TEXT("ZoomAnimMs"), Value, IniFile)) { ZoomAnimSeconds = Value / 1000.0f; bAny = true; }
  if (GConfig->GetFloat(Section, TEXT("OverviewReturnMs"), Value, IniFile)) { OverviewReturnSeconds = Value / 1000.0f; bAny = true; }
  if (GConfig->GetFloat(Section, TEXT("FollowFromZoom"), Value, IniFile)) { FollowFromZoom = Value; bAny = true; }
  if (bAny) Source += TEXT("+ini");
}

void FS08CameraZoomConfig::ApplyCommandLine(const TCHAR* CommandLine) {
  if (!CommandLine) return;
  bool bAny = false;
  float Value = 0.0f;
  if (FParse::Value(CommandLine, TEXT("S08CameraMinDist="), Value)) { MinDistanceUU = Value; bAny = true; }
  if (FParse::Value(CommandLine, TEXT("S08CameraOutRatio="), Value)) { OverviewOutRatio = Value; bAny = true; }
  if (FParse::Value(CommandLine, TEXT("S08CameraStep="), Value)) { WheelStepFactor = Value; bAny = true; }
  if (FParse::Value(CommandLine, TEXT("S08CameraAnimMs="), Value)) { ZoomAnimSeconds = Value / 1000.0f; bAny = true; }
  if (FParse::Value(CommandLine, TEXT("S08CameraReturnMs="), Value)) { OverviewReturnSeconds = Value / 1000.0f; bAny = true; }
  if (FParse::Value(CommandLine, TEXT("S08CameraFollowFrom="), Value)) { FollowFromZoom = Value; bAny = true; }
  if (bAny) Source += TEXT("+cli");
}

FString FS08CameraZoomConfig::Describe() const {
  return FString::Printf(
      TEXT("minDist=%.1f outRatio=%.3f step=%.3f animMs=%.0f returnMs=%.0f followFrom=%.2f source=%s issues=%d%s%s"),
      MinDistanceUU, OverviewOutRatio, WheelStepFactor, ZoomAnimSeconds * 1000.0f,
      OverviewReturnSeconds * 1000.0f, FollowFromZoom, *Source, Issues.Num(),
      Issues.Num() > 0 ? TEXT(" ") : TEXT(""), *FString::Join(Issues, TEXT("; ")));
}

void FS08CameraZoom::Reset(float OverviewDistance) {
  Overview = FMath::Max(0.0f, OverviewDistance);
  Current = Target = DistStart = Overview;
  DistElapsed = DistDuration = 0.0f;
  CurrentFocus = TargetFocus = FocusStart = FVector::ZeroVector;
  FocusElapsed = FocusDuration = 0.0f;
  LastCommandSeconds = Config.ZoomAnimSeconds;
}

float FS08CameraZoom::MinDistance() const {
  // Never above the overview: a tiny board must still allow the overview.
  return FMath::Min(Config.MinDistanceUU, Overview);
}

float FS08CameraZoom::MaxDistance() const {
  return Config.OverviewOutRatio > 0.0f ? Overview / Config.OverviewOutRatio : Overview;
}

FS08ZoomStep FS08CameraZoom::StartDistanceTween(float Requested, float Lo, float Hi, float Seconds) {
  FS08ZoomStep Step;
  Step.From = Target;
  Step.Requested = Requested;
  Step.To = FMath::Clamp(Requested, Lo, Hi);
  // A request beyond a limit, or a notch while already sitting on it.
  const float Tolerance = 0.01f;
  if (Requested < Lo - Tolerance || (Requested < Step.From && Step.From <= Lo + Tolerance)) {
    Step.bClamped = Requested < Lo - Tolerance || FMath::IsNearlyEqual(Step.From, Lo, Tolerance);
    Step.Limit = Step.bClamped ? ES08ZoomLimit::Near : ES08ZoomLimit::None;
  } else if (Requested > Hi + Tolerance || (Requested > Step.From && Step.From >= Hi - Tolerance)) {
    Step.bClamped = Requested > Hi + Tolerance || FMath::IsNearlyEqual(Step.From, Hi, Tolerance);
    Step.Limit = Step.bClamped ? ES08ZoomLimit::Far : ES08ZoomLimit::None;
  }
  Step.Seconds = Seconds;
  Target = Step.To;
  DistStart = Current;
  DistElapsed = 0.0f;
  DistDuration = Seconds;
  LastCommandSeconds = Seconds;
  return Step;
}

FS08ZoomStep FS08CameraZoom::Wheel(int32 Direction) {
  const float Factor = Config.WheelStepFactor;
  const float Requested = Direction > 0 ? Target / Factor : Target * Factor;
  return StartDistanceTween(Requested, MinDistance(), MaxDistance(), Config.ZoomAnimSeconds);
}

FS08ZoomStep FS08CameraZoom::ReturnToOverview() {
  return StartDistanceTween(Overview, MinDistance(), MaxDistance(), Config.OverviewReturnSeconds);
}

FS08ZoomStep FS08CameraZoom::FocusZoom(float Zoom) {
  const float Requested = Zoom > 0.0f ? Overview / Zoom : Overview;
  return StartDistanceTween(Requested, MinDistance(), Overview, Config.ZoomAnimSeconds);
}

void FS08CameraZoom::SetFocusTarget(const FVector& Focus) {
  if (Focus.Equals(TargetFocus, 0.01f)) return;
  TargetFocus = Focus;
  FocusStart = CurrentFocus;
  FocusElapsed = 0.0f;
  FocusDuration = LastCommandSeconds;
}

namespace {
float S08Smoothstep(float T) {
  const float X = FMath::Clamp(T, 0.0f, 1.0f);
  return X * X * (3.0f - 2.0f * X);
}
}  // namespace

void FS08CameraZoom::Tick(float DeltaSeconds) {
  const float Dt = FMath::Max(0.0f, DeltaSeconds);
  if (DistDuration > 0.0f && DistElapsed < DistDuration) {
    DistElapsed = FMath::Min(DistDuration, DistElapsed + Dt);
    Current = FMath::Lerp(DistStart, Target, S08Smoothstep(DistElapsed / DistDuration));
    if (DistElapsed >= DistDuration) Current = Target;
  } else {
    Current = Target;
  }
  if (FocusDuration > 0.0f && FocusElapsed < FocusDuration) {
    FocusElapsed = FMath::Min(FocusDuration, FocusElapsed + Dt);
    CurrentFocus = FMath::Lerp(FocusStart, TargetFocus, S08Smoothstep(FocusElapsed / FocusDuration));
    if (FocusElapsed >= FocusDuration) CurrentFocus = TargetFocus;
  } else {
    CurrentFocus = TargetFocus;
  }
}

bool FS08CameraZoom::WantsFollow() const {
  return Target > 0.0f && Overview / Target >= Config.FollowFromZoom - KINDA_SMALL_NUMBER;
}

bool FS08CameraZoom::IsSettled() const {
  return FMath::IsNearlyEqual(Current, Target, 0.001f) && CurrentFocus.Equals(TargetFocus, 0.001f);
}

// ------------------------------------------------------------ screen geometry

double FS08ScreenRect::IntersectionArea(const FS08ScreenRect& Other) const {
  const double W = FMath::Min(X1, Other.X1) - FMath::Max(X0, Other.X0);
  const double H = FMath::Min(Y1, Other.Y1) - FMath::Max(Y0, Other.Y0);
  return (W > 0.0 && H > 0.0) ? W * H : 0.0;
}

FS08ScreenRect FS08ScreenRect::FromPoints(const TArray<FVector2D>& Points) {
  if (Points.Num() == 0) return FS08ScreenRect();
  FS08ScreenRect R(Points[0].X, Points[0].Y, Points[0].X, Points[0].Y);
  for (const FVector2D& P : Points) {
    R.X0 = FMath::Min(R.X0, static_cast<float>(P.X));
    R.Y0 = FMath::Min(R.Y0, static_cast<float>(P.Y));
    R.X1 = FMath::Max(R.X1, static_cast<float>(P.X));
    R.Y1 = FMath::Max(R.Y1, static_cast<float>(P.Y));
  }
  return R;
}

namespace S08ArtHud {

TArray<FVector2D> ClipPolygonToRect(const TArray<FVector2D>& Polygon, const FS08ScreenRect& Rect) {
  // Same edge order and inside tests as qa010lib/geometry.clip_polygon_to_rect.
  TArray<FVector2D> Out = Polygon;
  for (int32 Edge = 0; Edge < 4 && Out.Num() > 0; ++Edge) {
    auto Inside = [&](const FVector2D& P) {
      switch (Edge) {
        case 0: return P.X >= Rect.X0;
        case 1: return P.X <= Rect.X1;
        case 2: return P.Y >= Rect.Y0;
        default: return P.Y <= Rect.Y1;
      }
    };
    auto Cross = [&](const FVector2D& A, const FVector2D& B) {
      const double Den = (Edge < 2) ? (B.X - A.X) : (B.Y - A.Y);
      const double Line = (Edge == 0) ? Rect.X0 : (Edge == 1) ? Rect.X1 : (Edge == 2) ? Rect.Y0 : Rect.Y1;
      const double T = FMath::Abs(Den) < 1e-12 ? 0.0 : ((Edge < 2 ? Line - A.X : Line - A.Y) / Den);
      return FVector2D(A.X + (B.X - A.X) * T, A.Y + (B.Y - A.Y) * T);
    };
    TArray<FVector2D> In = MoveTemp(Out);
    Out.Reset();
    for (int32 I = 0; I < In.Num(); ++I) {
      const FVector2D& Cur = In[I];
      const FVector2D& Prev = In[(I + In.Num() - 1) % In.Num()];
      const bool bCur = Inside(Cur);
      const bool bPrev = Inside(Prev);
      if (bCur) {
        if (!bPrev) Out.Add(Cross(Prev, Cur));
        Out.Add(Cur);
      } else if (bPrev) {
        Out.Add(Cross(Prev, Cur));
      }
    }
  }
  return Out;
}

double PolygonArea(const TArray<FVector2D>& Polygon) {
  if (Polygon.Num() < 3) return 0.0;
  double Sum = 0.0;
  for (int32 I = 0; I < Polygon.Num(); ++I) {
    const FVector2D& A = Polygon[I];
    const FVector2D& B = Polygon[(I + 1) % Polygon.Num()];
    Sum += static_cast<double>(A.X) * B.Y - static_cast<double>(B.X) * A.Y;
  }
  return FMath::Abs(Sum) * 0.5;
}

int32 CountOverlaps(const FS08ScreenRect& Rect, const TArray<FS08CellQuad>& Cells, double Epsilon,
                    TArray<FIntPoint>* OutCells, double* OutArea) {
  int32 Count = 0;
  double Total = 0.0;
  if (OutCells) OutCells->Reset();
  if (Rect.IsEmpty()) {
    if (OutArea) *OutArea = 0.0;
    return 0;
  }
  for (const FS08CellQuad& Quad : Cells) {
    if (Quad.Screen.Num() < 3) continue;
    const double Area = PolygonArea(ClipPolygonToRect(Quad.Screen, Rect));
    if (Area > Epsilon) {
      ++Count;
      Total += Area;
      if (OutCells) OutCells->Add(Quad.Cell);
    }
  }
  if (OutArea) *OutArea = Total;
  return Count;
}

FPlacementResult ChoosePlateRect(const FPlacementInput& In) {
  // Ring search around the anchor box: ring g holds every plate position whose
  // gap to the anchor is g along one axis and <= g along the other (the plate
  // slides along each side). The first ring with a clean candidate wins, and
  // inside it the candidate whose centre is nearest to the anchor centre (tie:
  // below, right, left, above). Nothing clean anywhere -> the least bad one
  // (forbidden count, forbidden area, soft area, ring).
  FPlacementResult Best;
  const float W = static_cast<float>(In.PlateSize.X);
  const float H = static_cast<float>(In.PlateSize.Y);
  if (W <= 0.0f || H <= 0.0f || In.Viewport.X <= 0.0 || In.Viewport.Y <= 0.0) return Best;
  const FS08ScreenRect View(In.EdgeMargin, In.EdgeMargin,
                            static_cast<float>(In.Viewport.X) - In.EdgeMargin,
                            static_cast<float>(In.Viewport.Y) - In.EdgeMargin);
  const float Step = FMath::Max(2.0f, In.Step);
  const FVector2D AC = In.Anchor.Center();
  // Bounding boxes of the forbidden quads: cheap reject before the clip.
  TArray<FS08ScreenRect> QuadBoxes;
  for (const FS08CellQuad& Q : In.Forbidden) QuadBoxes.Add(FS08ScreenRect::FromPoints(Q.Screen));
  auto Evaluate = [&](float X0, float Y0, const TCHAR* Side, int32 Ring, FPlacementResult& Out) -> bool {
    X0 = FMath::RoundToFloat(X0);
    Y0 = FMath::RoundToFloat(Y0);
    const FS08ScreenRect Rect(X0, Y0, X0 + W, Y0 + H);
    if (!View.Contains(Rect)) return false;
    Out = FPlacementResult();
    Out.Rect = Rect;
    Out.Candidate = Side;
    Out.Ring = Ring;
    const FS08ScreenRect Grown = Rect.Expand(In.Margin);
    TArray<FS08CellQuad> Near;
    for (int32 I = 0; I < In.Forbidden.Num(); ++I) {
      if (QuadBoxes[I].IntersectionArea(Grown) > 0.0) Near.Add(In.Forbidden[I]);
    }
    Out.ForbiddenOverlaps = Near.Num() > 0
        ? CountOverlaps(Grown, Near, OverlapEpsilonPx2, nullptr, &Out.ForbiddenArea) : 0;
    for (const FS08ScreenRect& Soft : In.Soft) Out.SoftArea += Rect.Expand(2.0f).IntersectionArea(Soft);
    Out.bBound = IsRectBoundTo(Rect, In.BindTarget, In.BindOthers);
    Out.bClean = Out.ForbiddenOverlaps == 0 && Out.SoftArea <= 0.0 && Out.bBound;
    return true;
  };
  bool bHaveBest = false;
  int32 Tested = 0;
  const int32 Rings = FMath::Max(1, In.Rings);
  for (int32 Ring = 0; Ring < Rings; ++Ring) {
    const float G = In.Gap + Ring * Step;
    FPlacementResult RingBest;
    double RingBestDist = TNumericLimits<double>::Max();
    int32 RingBestSide = 99;
    // Side order doubles as the tie-break preference.
    for (int32 Side = 0; Side < 4; ++Side) {
      const bool bVertical = Side == 0 || Side == 3;  // below / above slide along x
      const float Lo = bVertical ? In.Anchor.X0 - W - G : In.Anchor.Y0 - H - G;
      const float Hi = bVertical ? In.Anchor.X1 + G : In.Anchor.Y1 + G;
      for (float S = Lo; S <= Hi + 0.01f; S += Step) {
        float X0 = 0.0f, Y0 = 0.0f;
        const TCHAR* Name = TEXT("below");
        switch (Side) {
          case 0: X0 = S; Y0 = In.Anchor.Y1 + G; Name = TEXT("below"); break;
          case 1: X0 = In.Anchor.X1 + G; Y0 = S; Name = TEXT("right"); break;
          case 2: X0 = In.Anchor.X0 - G - W; Y0 = S; Name = TEXT("left"); break;
          default: X0 = S; Y0 = In.Anchor.Y0 - G - H; Name = TEXT("above"); break;
        }
        FPlacementResult Try;
        if (!Evaluate(X0, Y0, Name, Ring, Try)) continue;
        ++Tested;
        if (Try.bClean) {
          const double Dist = FVector2D::Distance(Try.Rect.Center(), AC);
          if (Dist < RingBestDist - 0.5 || (FMath::Abs(Dist - RingBestDist) <= 0.5 && Side < RingBestSide)) {
            RingBest = Try;
            RingBestDist = Dist;
            RingBestSide = Side;
          }
          continue;
        }
        // least bad: forbidden count, forbidden area, then bound before unbound, then soft area
        const bool bBetter = !bHaveBest ||
            Try.ForbiddenOverlaps < Best.ForbiddenOverlaps ||
            (Try.ForbiddenOverlaps == Best.ForbiddenOverlaps &&
             (Try.ForbiddenArea < Best.ForbiddenArea - 0.5 ||
              (FMath::Abs(Try.ForbiddenArea - Best.ForbiddenArea) <= 0.5 &&
               ((Try.bBound && !Best.bBound) ||
                (Try.bBound == Best.bBound && Try.SoftArea < Best.SoftArea - 0.5)))));
        if (bBetter) {
          Best = Try;
          bHaveBest = true;
        }
      }
    }
    if (RingBest.bClean) {
      RingBest.Tested = Tested;
      return RingBest;
    }
  }
  // W7 on-owner pass (GD-058 interim §8 item 13): nothing clean and the least bad place is not bound to the owner ->
  // a plate ON the owner's box reads as the owner's (rect gap 0 to it, > 0 to every other figure). It stays off every
  // destination cell; among such places: least overlap with soft obstacles other than the owner (HUD panels), then
  // the plate's bottom-centre nearest to the owner's top-centre: the plain nameplate "above the head", slid down into
  // the figure box only as far as the destination cells and the neighbours force it. The box top is the figure height
  // (headroom above the sculpture), and the team ring / selection mark at the base stay visible.
  if (In.bAllowOnOwner && !In.BindTarget.IsEmpty() && !In.Anchor.IsEmpty() &&
      !(bHaveBest && Best.ForbiddenOverlaps == 0 && Best.bBound)) {
    const float Fine = FMath::Max(2.0f, Step * 0.5f);
    const FVector2D Head(AC.X, In.Anchor.Y0);
    FPlacementResult OnBest;
    bool bHaveOn = false;
    double OnBestOther = 0.0, OnBestDist = 0.0;
    for (float Y0 = In.Anchor.Y0 - H + 1.0f; Y0 <= In.Anchor.Y1 - 1.0f; Y0 += Fine) {
      for (float X0 = In.Anchor.X0 - W + 1.0f; X0 <= In.Anchor.X1 - 1.0f; X0 += Fine) {
        FPlacementResult Try;
        if (!Evaluate(X0, Y0, TEXT("on-owner"), 0, Try)) continue;
        ++Tested;
        if (Try.ForbiddenOverlaps != 0 || !Try.bBound) continue;
        double Other = 0.0;
        const FS08ScreenRect Grown = Try.Rect.Expand(2.0f);
        for (const FS08ScreenRect& Soft : In.Soft) {
          const bool bOwner = FMath::IsNearlyEqual(Soft.X0, In.Anchor.X0) && FMath::IsNearlyEqual(Soft.Y0, In.Anchor.Y0) &&
                              FMath::IsNearlyEqual(Soft.X1, In.Anchor.X1) && FMath::IsNearlyEqual(Soft.Y1, In.Anchor.Y1);
          if (!bOwner) Other += Grown.IntersectionArea(Soft);
        }
        const double Dist = FVector2D::Distance(FVector2D(Try.Rect.Center().X, Try.Rect.Y1), Head);
        if (!bHaveOn || Other < OnBestOther - 0.5 ||
            (FMath::Abs(Other - OnBestOther) <= 0.5 && Dist < OnBestDist - 0.01)) {
          OnBest = Try;
          OnBestOther = Other;
          OnBestDist = Dist;
          bHaveOn = true;
        }
      }
    }
    if (bHaveOn) {
      OnBest.Tested = Tested;
      return OnBest;
    }
  }
  Best.Tested = Tested;
  return Best;
}

double OverlapArea(const FS08ScreenRect& A, const TArray<FS08ScreenRect>& Others) {
  double Sum = 0.0;
  for (const FS08ScreenRect& O : Others) {
    if (!O.IsEmpty()) Sum += A.IntersectionArea(O);
  }
  return Sum;
}

double PointRectDistance(const FVector2D& P, const FS08ScreenRect& R) {
  const double Dx = FMath::Max3(static_cast<double>(R.X0) - P.X, 0.0, P.X - static_cast<double>(R.X1));
  const double Dy = FMath::Max3(static_cast<double>(R.Y0) - P.Y, 0.0, P.Y - static_cast<double>(R.Y1));
  return FMath::Sqrt(Dx * Dx + Dy * Dy);
}

bool IsBoundTo(const FVector2D& P, const FS08ScreenRect& Target, const TArray<FS08ScreenRect>& Others) {
  if (Target.IsEmpty()) return true;
  const double D = PointRectDistance(P, Target);
  for (const FS08ScreenRect& O : Others) {
    if (!O.IsEmpty() && PointRectDistance(P, O) <= D) return false;
  }
  return true;
}

double RectGap(const FS08ScreenRect& A, const FS08ScreenRect& B) {
  const double Dx = FMath::Max3(static_cast<double>(B.X0) - A.X1, 0.0, static_cast<double>(A.X0) - B.X1);
  const double Dy = FMath::Max3(static_cast<double>(B.Y0) - A.Y1, 0.0, static_cast<double>(A.Y0) - B.Y1);
  return FMath::Sqrt(Dx * Dx + Dy * Dy);
}

bool IsRectBoundTo(const FS08ScreenRect& R, const FS08ScreenRect& Target, const TArray<FS08ScreenRect>& Others) {
  if (Target.IsEmpty()) return true;
  const double D = RectGap(R, Target);
  for (const FS08ScreenRect& O : Others) {
    if (!O.IsEmpty() && RectGap(R, O) <= D) return false;
  }
  return true;
}

FLabelPlacementResult ChooseLabelRect(const FLabelPlacementInput& In) {
  FLabelPlacementResult Best;
  const float W = static_cast<float>(In.Size.X);
  const float H = static_cast<float>(In.Size.Y);
  if (W <= 0.0f || H <= 0.0f || In.Viewport.X <= 0.0 || In.Viewport.Y <= 0.0) return Best;
  const FS08ScreenRect View(In.EdgeMargin, In.EdgeMargin, static_cast<float>(In.Viewport.X) - In.EdgeMargin,
                            static_cast<float>(In.Viewport.Y) - In.EdgeMargin);
  const float Step = FMath::Max(2.0f, In.Step);
  const float Cx = static_cast<float>(In.Anchor.Center().X);
  bool bHaveHardClean = false, bHaveAny = false;
  FLabelPlacementResult BestHardClean, BestAny;
  int32 Tested = 0;
  auto Try = [&](float X0, float Y0, const TCHAR* Name, int32 Ring) -> bool {
    X0 = FMath::RoundToFloat(X0);
    Y0 = FMath::RoundToFloat(Y0);
    const FS08ScreenRect Rect(X0, Y0, X0 + W, Y0 + H);
    if (!View.Contains(Rect)) return false;
    ++Tested;
    FLabelPlacementResult R;
    R.Rect = Rect;
    R.Candidate = Name;
    R.Ring = Ring;
    R.HardArea = OverlapArea(Rect, In.Hard);
    R.SoftArea = OverlapArea(Rect, In.Soft);
    R.bBound = IsBoundTo(Rect.Center(), In.BindTarget, In.BindOthers);
    R.bHardClean = R.HardArea <= 0.5 && R.bBound;
    R.bClean = R.bHardClean && R.SoftArea <= 0.5;
    if (R.bClean) {
      Best = R;
      return true;
    }
    if (R.bHardClean && (!bHaveHardClean || R.SoftArea < BestHardClean.SoftArea - 0.5)) {
      BestHardClean = R;
      bHaveHardClean = true;
    }
    // unbound candidates rank after every bound one (a large fixed penalty keeps the order deterministic)
    const double Rank = R.HardArea + (R.bBound ? 0.0 : 1e9);
    const double BestRank = BestAny.HardArea + (BestAny.bBound ? 0.0 : 1e9);
    if (!bHaveAny || Rank < BestRank - 0.5 ||
        (FMath::Abs(Rank - BestRank) <= 0.5 && R.SoftArea < BestAny.SoftArea - 0.5)) {
      BestAny = R;
      bHaveAny = true;
    }
    return false;
  };
  for (int32 Ring = 0; Ring < FMath::Max(1, In.Rings); ++Ring) {
    const float G = In.Gap + Ring * Step;
    const int32 Slides = Ring + 1;
    if (In.bRightFirst) {
      // right of the anchor, vertically centred on it, then sliding down/up
      for (int32 K = 0; K < 2 * Slides - 1; ++K) {
        const int32 Off = (K + 1) / 2 * ((K % 2) ? 1 : -1);
        if (Try(In.Anchor.X1 + G, static_cast<float>(In.Anchor.Center().Y) - H * 0.5f + Off * Step, TEXT("right"),
                Ring)) {
          Best.Tested = Tested;
          return Best;
        }
      }
    }
    // above: centred, then alternating left/right slides
    for (int32 K = 0; K < 2 * Slides - 1; ++K) {
      const int32 Off = (K + 1) / 2 * ((K % 2) ? 1 : -1);
      if (Try(Cx - W * 0.5f + Off * Step, In.Anchor.Y0 - G - H, TEXT("above"), Ring)) {
        Best.Tested = Tested;
        return Best;
      }
    }
    // right: top-aligned to the anchor top, sliding down
    for (int32 K = 0; K < Slides && !In.bRightFirst; ++K) {
      if (Try(In.Anchor.X1 + G, In.Anchor.Y0 + K * Step, TEXT("right"), Ring)) {
        Best.Tested = Tested;
        return Best;
      }
    }
    for (int32 K = 0; K < Slides; ++K) {
      if (Try(In.Anchor.X0 - G - W, In.Anchor.Y0 + K * Step, TEXT("left"), Ring)) {
        Best.Tested = Tested;
        return Best;
      }
    }
    for (int32 K = 0; K < 2 * Slides - 1; ++K) {
      const int32 Off = (K + 1) / 2 * ((K % 2) ? 1 : -1);
      if (Try(Cx - W * 0.5f + Off * Step, In.Anchor.Y1 + G, TEXT("below"), Ring)) {
        Best.Tested = Tested;
        return Best;
      }
    }
    // W5b-R r3: inset - centred, flush with the top of the owner's own box (tags only; see bInset)
    if (In.bInset && Ring == 0) {
      if (Try(Cx - W * 0.5f, In.Anchor.Y0, TEXT("inset"), Ring)) {
        Best.Tested = Tested;
        return Best;
      }
    }
    // W5b-R r3: near rings - a bound hard-clean candidate here beats a clean one further out
    if (In.NearRings > 0 && Ring + 1 >= In.NearRings && bHaveHardClean) {
      BestHardClean.Tested = Tested;
      return BestHardClean;
    }
  }
  Best = bHaveHardClean ? BestHardClean : BestAny;
  Best.Tested = Tested;
  return Best;
}

FLabelPlacementInput MakeTagPlacementInput(const FVector2D& Viewport, const FVector2D& Size, const FS08ScreenRect& Owner,
                                           const TArray<FS08ScreenRect>& Others, const TArray<FS08ScreenRect>& Hard) {
  FLabelPlacementInput In;
  In.Viewport = Viewport;
  In.Size = Size;
  In.Anchor = Owner;
  In.Hard = Hard;
  In.Soft = Others;
  // t53 revision 1 tags.binding: the tag reads as its owner's (the W5b-R G3 Medusa tag sat 98 px away, next to the
  // Harpies 2 tag, because nothing bound it)
  In.BindTarget = Owner;
  In.BindOthers = Others;
  In.bInset = true;
  In.NearRings = 2;
  return In;
}

FIconAnchorResult ChooseIconAnchor(const FIconAnchorInput& In) {
  FIconAnchorResult Out;
  const float N = In.Size;
  if (N <= 0.0f || In.Viewport.X <= 0.0 || In.Viewport.Y <= 0.0 || In.Target.IsEmpty()) return Out;
  const FS08ScreenRect View(In.EdgeMargin, In.EdgeMargin, static_cast<float>(In.Viewport.X) - In.EdgeMargin,
                            static_cast<float>(In.Viewport.Y) - In.EdgeMargin);
  const FS08ScreenRect& T = In.Target;
  const float Cy35 = T.Y0 + 0.35f * T.Height();
  const float Cx = static_cast<float>(T.Center().X);
  struct FCand {
    const TCHAR* Name;
    float X0, Y0;
  };
  const FCand Cands[] = {{TEXT("right"), T.X1 + In.Gap, Cy35 - N * 0.5f},
                         {TEXT("left"), T.X0 - In.Gap - N, Cy35 - N * 0.5f},
                         {TEXT("below"), Cx - N * 0.5f, T.Y1 + In.Gap},
                         {TEXT("above"), Cx - N * 0.5f, T.Y0 - In.Gap - N}};
  TArray<FS08ScreenRect> Obstacles = In.Figures;
  Obstacles.Append(In.Hard);
  for (const FCand& C : Cands) {
    const float X0 = FMath::RoundToFloat(C.X0), Y0 = FMath::RoundToFloat(C.Y0);
    const FS08ScreenRect Rect(X0, Y0, X0 + N, Y0 + N);
    ++Out.Tested;
    if (!View.Contains(Rect)) continue;
    if (OverlapArea(Rect, Obstacles) > 0.5) continue;
    Out.Rect = Rect;
    Out.Anchor = C.Name;
    return Out;
  }
  // every anchor is taken: above the figure (clamped into the viewport), the overlap is recorded
  const float X0 = FMath::Clamp(FMath::RoundToFloat(Cx - N * 0.5f), View.X0, FMath::Max(View.X0, View.X1 - N));
  const float Y0 = FMath::Clamp(FMath::RoundToFloat(T.Y0 - In.Gap - N), View.Y0, FMath::Max(View.Y0, View.Y1 - N));
  Out.Rect = FS08ScreenRect(X0, Y0, X0 + N, Y0 + N);
  Out.Anchor = TEXT("above");
  Out.bFallback = true;
  Out.OverlapArea = OverlapArea(Out.Rect, Obstacles);
  return Out;
}

FString FormatCells(const TArray<FIntPoint>& Cells) {
  FString Out;
  for (const FIntPoint& Cell : Cells) Out += FString::Printf(TEXT("(%d,%d)"), Cell.X, Cell.Y);
  return Out;
}

FString FormatRect(const FS08ScreenRect& Rect) {
  return FString::Printf(TEXT("(%d,%d,%d,%d)"), FMath::RoundToInt(Rect.X0), FMath::RoundToInt(Rect.Y0),
                         FMath::RoundToInt(Rect.X1), FMath::RoundToInt(Rect.Y1));
}

FString FormatWidgetLine(const FString& Id, const TCHAR* Impl, const TCHAR* State, const FString& Fighter,
                         const FS08ScreenRect& Rect, bool bPainted, bool bTwin, const FString& Source) {
  return FString::Printf(
      TEXT("SHOT widget id=%s impl=%s state=%s fighter=%s bbox=%s geom=%s visible=%d twin=%d source=%s"), *Id, Impl,
      (State && *State) ? State : TEXT("none"), Fighter.IsEmpty() ? TEXT("none") : *Fighter,
      *FormatRect(bPainted ? Rect : FS08ScreenRect()), bPainted ? TEXT("painted") : TEXT("unpainted"), bTwin ? 0 : 1,
      bTwin ? 1 : 0, Source.IsEmpty() ? TEXT("none") : *Source);
}

FString FormatWidgetLineEx(const FString& Id, const TCHAR* Impl, const TCHAR* State, const FString& Fighter,
                           const FS08ScreenRect& Rect, bool bPainted, bool bVisible, const FString& Source,
                           const FString& Extra) {
  return FString::Printf(
      TEXT("SHOT widget id=%s impl=%s state=%s fighter=%s bbox=%s geom=%s visible=%d twin=0 source=%s%s%s"), *Id, Impl,
      (State && *State) ? State : TEXT("none"), Fighter.IsEmpty() ? TEXT("none") : *Fighter,
      *FormatRect(bPainted ? Rect : FS08ScreenRect()), bPainted ? TEXT("painted") : TEXT("unpainted"), bVisible ? 1 : 0,
      Source.IsEmpty() ? TEXT("none") : *Source, Extra.IsEmpty() ? TEXT("") : TEXT(" "), *Extra);
}

void SortCells(TArray<FIntPoint>& Cells) {
  Cells.Sort([](const FIntPoint& A, const FIntPoint& B) {
    return A.Y != B.Y ? A.Y < B.Y : A.X < B.X;
  });
}

TArray<FIntPoint> DestinationCells(const TSet<uint64>& LegalCells, const FIntPoint& OwnCell) {
  TArray<FIntPoint> Out;
  for (const uint64 Key : LegalCells) {
    const FIntPoint Cell(static_cast<int32>(Key >> 32), static_cast<int32>(Key & 0xFFFFFFFF));
    if (Cell == OwnCell) continue;
    Out.Add(Cell);
  }
  SortCells(Out);
  return Out;
}

}  // namespace S08ArtHud

bool FS08PinholeCamera::Project(const FVector& World, FVector2D& OutScreen) const {
  const FRotationMatrix M(Rotation);
  const FVector Forward = M.GetScaledAxis(EAxis::X);
  const FVector Right = M.GetScaledAxis(EAxis::Y);
  const FVector Up = M.GetScaledAxis(EAxis::Z);
  const FVector D = World - Position;
  const double Depth = FVector::DotProduct(D, Forward);
  if (Depth <= 10.0) return false;  // UE default near clip
  const double Focal = (Viewport.X * 0.5) / FMath::Tan(FMath::DegreesToRadians(HorizontalFovDeg) * 0.5);
  OutScreen.X = Viewport.X * 0.5 + FVector::DotProduct(D, Right) / Depth * Focal;
  OutScreen.Y = Viewport.Y * 0.5 - FVector::DotProduct(D, Up) / Depth * Focal;
  return true;
}

// ------------------------------------------------------------- input & flags

const TCHAR* S08InputStepName(ES08InputStep Step) {
  switch (Step) {
    case ES08InputStep::WheelIn: return TEXT("wheelin");
    case ES08InputStep::WheelOut: return TEXT("wheelout");
    case ES08InputStep::Space: return TEXT("space");
    case ES08InputStep::ClickHero: return TEXT("clickhero");
    case ES08InputStep::ClickAbove: return TEXT("clickabove");
    case ES08InputStep::ClickCell: return TEXT("clickcell");
  }
  return TEXT("unknown");
}

bool S08ParseInputPlan(const FString& Text, TArray<ES08InputStep>& OutSteps, FString& OutError) {
  OutSteps.Reset();
  OutError.Reset();
  TArray<FString> Tokens;
  Text.ParseIntoArray(Tokens, TEXT("+"), true);
  if (Tokens.Num() == 0) {
    OutError = TEXT("empty plan");
    return false;
  }
  for (FString Token : Tokens) {
    Token = Token.TrimStartAndEnd().ToLower();
    int32 Repeat = 1;
    FString Name = Token;
    int32 Star = INDEX_NONE;
    if (Token.FindChar(TEXT('*'), Star)) {
      Name = Token.Left(Star);
      const FString Count = Token.Mid(Star + 1);
      if (!Count.IsNumeric()) {
        OutError = FString::Printf(TEXT("bad repeat in '%s'"), *Token);
        return false;
      }
      Repeat = FCString::Atoi(*Count);
      if (Repeat < 1 || Repeat > 20) {
        OutError = FString::Printf(TEXT("repeat %d outside 1..20 in '%s'"), Repeat, *Token);
        return false;
      }
    }
    ES08InputStep Step;
    if (Name == TEXT("wheelin")) Step = ES08InputStep::WheelIn;
    else if (Name == TEXT("wheelout")) Step = ES08InputStep::WheelOut;
    else if (Name == TEXT("space")) Step = ES08InputStep::Space;
    else if (Name == TEXT("clickhero")) Step = ES08InputStep::ClickHero;
    else if (Name == TEXT("clickabove")) Step = ES08InputStep::ClickAbove;
    else if (Name == TEXT("clickcell")) Step = ES08InputStep::ClickCell;
    else {
      OutError = FString::Printf(TEXT("unknown step '%s'"), *Name);
      OutSteps.Reset();
      return false;
    }
    for (int32 I = 0; I < Repeat; ++I) OutSteps.Add(Step);
    if (OutSteps.Num() > 40) {
      OutError = TEXT("more than 40 steps");
      OutSteps.Reset();
      return false;
    }
  }
  return true;
}

int32 S08ParseIconSize(const FString& Text, int32 Default) {
  const FString T = Text.TrimStartAndEnd();
  if (T.IsEmpty()) return Default;
  if (!T.IsNumeric()) return 0;
  const int32 Value = FCString::Atoi(*T);
  return (Value == 24 || Value == 32 || Value == 48) ? Value : 0;
}

bool S08IsMedusaCandidateFighter(bool bArtPreview, bool bAllMedusa, bool bIsHero, const FString& Name) {
  if (!bArtPreview) return false;
  if (bAllMedusa) return true;
  return bIsHero && Name.Equals(TEXT("Medusa"), ESearchCase::IgnoreCase);
}

bool FS08SeqDedupe::Accept(const FString& FighterId, int32 Seq) {
  const FString K = Key(FighterId, Seq);
  if (Seen.Contains(K)) return false;
  Seen.Add(K);
  return true;
}

TArray<FString> S08PlateStatuses(bool bIsHero, bool bOwn, const FString& AttackType, bool bAttacker,
                                 bool bTarget, const TArray<FString>& Effects) {
  TArray<FString> Out;
  Out.Add(bIsHero ? TEXT("HERO") : TEXT("SIDEKICK"));
  if (!AttackType.IsEmpty()) Out.Add(AttackType.ToUpper());
  if (bAttacker) Out.Add(TEXT("ATTACKER"));
  if (bTarget) Out.Add(TEXT("TARGET"));
  for (const FString& Effect : Effects) {
    const FString E = Effect.TrimStartAndEnd();
    if (!E.IsEmpty()) Out.Add(E.ToUpper());
  }
  (void)bOwn;  // team is shown by its own chip, not as a status
  return Out;
}

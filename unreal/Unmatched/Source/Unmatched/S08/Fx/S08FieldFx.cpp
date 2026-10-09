// VS-6 F1: see S08FieldFx.h.
#include "S08FieldFx.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Crc.h"
#include "Misc/Parse.h"
#include "TimerManager.h"
#include "../S08HudTokens.generated.h"
#include "../S08IconMotion.h"
#include "../S08Render.h"
#include "../S08TraceLog.h"

namespace S08FieldFx {

namespace {
TOptional<uint32> GLegacyOverride;

bool LegacyBit(uint32 Bit, const TCHAR* Flag) {
  if (GLegacyOverride.IsSet()) return (GLegacyOverride.GetValue() & Bit) != 0;
  return FParse::Param(FCommandLine::Get(), Flag);
}

float Clamp01(double X) { return static_cast<float>(FMath::Clamp(X, 0.0, 1.0)); }
float EaseOut(double X) {
  const double C = FMath::Clamp(X, 0.0, 1.0);
  return static_cast<float>(1.0 - (1.0 - C) * (1.0 - C));
}
}  // namespace

bool ChoiceLegacy() { return LegacyBit(Choice, ChoiceLegacyFlag); }
bool PulseLegacy() { return LegacyBit(Pulse, MovePlatesLegacyFlag); }
bool LastMoveLegacy() { return LegacyBit(LastMove, LastMoveLegacyFlag); }
bool TargetArcLegacy() { return LegacyBit(TargetArc, TargetArcLegacyFlag); }
bool ChoiceLayerWanted() { return !ChoiceLegacy() || !LastMoveLegacy() || !PulseLegacy(); }
void SetLegacyOverrideForTest(uint32 Mask) { GLegacyOverride = Mask; }
void ResetLegacyOverrideForTest() { GLegacyOverride.Reset(); }

FString ArtLookToken() {
  TArray<FString> Off;
  if (ChoiceLegacy()) Off.Add(TEXT("-S08ChoiceLegacy"));
  if (PulseLegacy()) Off.Add(TEXT("-S08MovePlatesLegacy"));
  if (LastMoveLegacy()) Off.Add(TEXT("-S08LastMoveLegacy"));
  if (TargetArcLegacy()) Off.Add(TEXT("-S08TargetArcLegacy"));
  return Off.Num() == 0 ? FString(TEXT("on")) : FString::Printf(TEXT("legacy(%s)"), *FString::Join(Off, TEXT(",")));
}

FMarkPose SelectionAppear(double Ms, bool bReduced) {
  FMarkPose P;
  if (bReduced) {
    P.Scale = 1.0f;
    P.Opacity = Clamp01(Ms / 100.0);
    P.bDone = Ms >= 100.0;
    return P;
  }
  const float E = EaseOut(Ms / 120.0);
  P.Scale = FMath::Lerp(0.85f, 1.0f, E);
  P.Opacity = E;
  P.bDone = Ms >= SelectionAppearMs;
  return P;
}

FMarkPose SelectionLeave(double Ms, bool bReduced) {
  const double Dur = bReduced ? 100.0 : SelectionLeaveMs;
  FMarkPose P;
  P.Scale = 1.0f;
  P.Opacity = 1.0f - Clamp01(Ms / Dur);
  P.bDone = Ms >= Dur;
  return P;
}

FMarkPose TargetAppear(double Ms, bool bReduced) {
  FMarkPose P;
  if (bReduced) {
    P.Opacity = Clamp01(Ms / 100.0);
    P.bDone = Ms >= 100.0;
    return P;
  }
  const float E = EaseOut(Ms / TargetAppearMs);
  P.Scale = FMath::Lerp(1.15f, 1.0f, E);
  P.Opacity = E;
  P.bDone = Ms >= TargetAppearMs;
  return P;
}

FMarkPose TargetLeave(double Ms, bool bReduced) {
  const double Dur = bReduced ? 100.0 : TargetLeaveMs;
  FMarkPose P;
  P.Opacity = 1.0f - Clamp01(Ms / Dur);
  P.bDone = Ms >= Dur;
  return P;
}

FPulsePose ConfirmPulse(double Ms, bool bReduced) {
  FPulsePose P;
  if (bReduced) {
    const float X = Clamp01(Ms / 100.0);
    P.Scale = 1.0f;
    P.Fill = 1.0f - X;
    P.Dim = FMath::Lerp(1.0f, 0.7f, X);
    P.bDone = Ms >= 100.0;
    return P;
  }
  const float E = EaseOut(Ms / ConfirmPulseMs);
  P.Scale = FMath::Lerp(1.06f, 1.0f, E);
  P.Fill = 1.0f - E;
  P.Dim = FMath::Lerp(1.0f, 0.7f, E);
  P.bDone = Ms >= ConfirmPulseMs;
  return P;
}

FMarkPose RefuseStamp(double Ms, bool bReduced) {
  FMarkPose P;
  if (bReduced) {
    P.Opacity = Ms < 30.0 ? Clamp01(Ms / 30.0) : (Ms < 70.0 ? 1.0f : 1.0f - Clamp01((Ms - 70.0) / 30.0));
    P.bDone = Ms >= 100.0;
    return P;
  }
  if (Ms < 80.0) {
    const float E = EaseOut(Ms / 80.0);
    P.Scale = FMath::Lerp(1.2f, 1.0f, E);
    P.Opacity = E;
  } else if (Ms < 230.0) {
    P.Opacity = 1.0f;
  } else {
    P.Opacity = 1.0f - Clamp01((Ms - 230.0) / 120.0);
  }
  P.bDone = Ms >= RefuseMs;
  return P;
}

float RefuseBadgePx(float CellDiameterPx) { return FMath::Clamp(0.3f * CellDiameterPx, 24.0f, 32.0f); }

float FadeIn(double Ms, double DurMs, bool bReduced) {
  const double D = bReduced ? FMath::Min(DurMs, 100.0) : DurMs;
  return D <= 0.0 ? 1.0f : Clamp01(Ms / D);
}

int32 DustCount(uint32 Seed) { return 3 + static_cast<int32>(Seed % 3u); }

FTransform DustTransform(const FVector& At) {
  const uint32 Seed =
      FCrc::StrCrc32(*FString::Printf(TEXT("%d,%d"), FMath::RoundToInt(At.X), FMath::RoundToInt(At.Y))) & 0x7FFFFFFF;
  const float S = 1.0f + 0.04f * static_cast<float>(DustCount(Seed) - 3);
  const float Yaw = static_cast<float>((Seed >> 4) % 360u);
  return FTransform(FRotator(0.0f, Yaw, 0.0f), At, FVector(S, S, 1.0f));
}

FDustDisc DustAt(double Ms, float SpreadUU) {
  // 0 ms: at the pedestal edge (16 uu), radius 6, opacity 1; 0-180: out to SpreadUU (20..35 by the seed), radius
  // -> 10; 180-300: opacity -> 0, radius -> 11
  FDustDisc D;
  const double T = FMath::Clamp(Ms, 0.0, DustMs);
  if (T < 180.0) {
    const float E = EaseOut(T / 180.0);
    D.DistUU = FMath::Lerp(16.0f, SpreadUU, E);
    D.RadiusUU = FMath::Lerp(6.0f, 10.0f, E);
    D.Opacity = 1.0f;
  } else {
    const float X = Clamp01((T - 180.0) / 120.0);
    D.DistUU = SpreadUU;
    D.RadiusUU = FMath::Lerp(10.0f, 11.0f, X);
    D.Opacity = 1.0f - X;
  }
  return D;
}

FMarkPose ChevronAt(int32 Index, double Ms) {
  FMarkPose P;
  const double Start = 120.0 * FMath::Clamp(Index, 0, 2);
  if (Ms < Start) {
    P.Scale = 0.6f;
    P.Opacity = 0.0f;
  } else if (Ms < Start + 80.0) {
    const float E = EaseOut((Ms - Start) / 80.0);
    P.Scale = FMath::Lerp(0.6f, 1.0f, E);
    P.Opacity = 1.0f;  // there from its start (t0 + 120 x I); the scale 0.6 -> 1.0 is the appear
  } else if (Ms < 480.0) {
    P.Opacity = 1.0f;
  } else {
    P.Opacity = 1.0f - Clamp01((Ms - 480.0) / 120.0);
  }
  P.bDone = Ms >= ChevronMs;
  return P;
}

float ChevronCutOpacity(double MsSinceCut) {
  return MsSinceCut <= 0.0 ? 1.0f : Clamp01(1.0 - MsSinceCut / ChevronCutMs);
}

double BenchChevronMs(double Ms, bool bReduced) { return bReduced ? FMath::Min(Ms * 6.0, 470.0) : Ms; }

float ChevronWidthUU(float LengthUU, float CellRadiusUU) {
  // neighbours (closer than 2.5 cell radii): >= 0.2 R; a far attack >= 0.35 R; never wider than 0.6 R
  const float Floor = (LengthUU < 2.5f * CellRadiusUU ? 0.2f : 0.35f) * CellRadiusUU;
  return FMath::Clamp(0.22f * LengthUU, Floor, 0.6f * CellRadiusUU);
}

}  // namespace S08FieldFx

// ------------------------------------------------------------------------------------------------- FS08FieldMarks

bool FS08FieldMarks::Bind(AActor* InOwner, UStaticMeshComponent* InRing, UStaticMeshComponent* InTargetRing) {
  using namespace S08FieldFx;
  Owner = InOwner;
  Ring = InRing;
  TargetRing = InTargetRing;
  bRingReady = false;
  bTargetReady = false;
  if (S08LegacyRender()) return false;
  if (InRing && !ChoiceLegacy()) {
    UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, SelectionRingMi, nullptr, LOAD_NoWarn);
    UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, PlaneMeshPath, nullptr, LOAD_NoWarn);
    if (Mi && Plane) {
      // FX-07 (ВР-FX12): the ring is drawn by M_FX_FieldMark on the engine plane (SDF in world uu: 2 x V-17 wide,
      // outer keyline board.keyline 1 uu) - one draw call like the mesh before, the shape no longer tied to it
      InRing->SetStaticMesh(Plane);
      UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Mi, InOwner);
      InRing->SetMaterial(0, Mid);
      InRing->SetTranslucentSortPriority(MarkSortPriority);
      Mid->SetVectorParameterValue(ParamColorBody, FLinearColor::FromSRGBColor(S08HudTokens::Color_BoardChoice));
      Mid->SetVectorParameterValue(ParamColorKeyline, FLinearColor::FromSRGBColor(S08HudTokens::Color_BoardKeyline));
      Mid->SetScalarParameterValue(ParamMode, 0.0f);
      Mid->SetScalarParameterValue(ParamRadiusIn, SelectionRadiusUU - 0.5f * SelectionWidthUU);
      Mid->SetScalarParameterValue(ParamRadiusOut, SelectionRadiusUU + 0.5f * SelectionWidthUU);
      Mid->SetScalarParameterValue(ParamKeylineUU, SelectionKeylineUU);
      Mid->SetScalarParameterValue(ParamOpacity, 0.0f);
      Mid->SetScalarParameterValue(ParamScale, 1.0f);
      RingMid = Mid;
      bRingReady = true;
    }
  }
  if (InTargetRing && !TargetArcLegacy()) {
    UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, TargetArcMi, nullptr, LOAD_NoWarn);
    UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, PlaneMeshPath, nullptr, LOAD_NoWarn);
    if (Mi && Plane) {
      // FX-15 (ВР-30, ВР-VS6-02): four board.target arcs with the mark.keyline edge, drawn by M_FX_FieldMark mode 2 on
      // the engine plane outside the team ring (the old mesh arcs sit inside it, too thin for a cream body + keyline)
      InTargetRing->SetStaticMesh(Plane);
      UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Mi, InOwner);
      InTargetRing->SetMaterial(0, Mid);
      InTargetRing->SetTranslucentSortPriority(MarkSortPriority);
      Mid->SetVectorParameterValue(ParamColorBody, FLinearColor::FromSRGBColor(S08HudTokens::Color_BoardTarget));
      Mid->SetVectorParameterValue(ParamColorKeyline, FLinearColor::FromSRGBColor(S08HudTokens::Color_MarkKeyline));
      Mid->SetScalarParameterValue(ParamMode, 2.0f);
      Mid->SetScalarParameterValue(ParamRadiusIn, TargetRadiusIn);
      Mid->SetScalarParameterValue(ParamRadiusOut, TargetRadiusOut);
      Mid->SetScalarParameterValue(ParamKeylineUU, TargetKeylineUU);
      Mid->SetScalarParameterValue(ParamArcSpan, TargetArcSpanDeg);
      Mid->SetScalarParameterValue(ParamOpacity, 0.0f);
      Mid->SetScalarParameterValue(ParamScale, 1.0f);
      TargetOuterUU = TargetRadiusOut + TargetKeylineUU;
      TargetMid = Mid;
      bTargetReady = true;
    }
  }
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW field-marks ring=%s target=%s outer=%.1f"),
                                   bRingReady ? TEXT("MI_FX_SelectionRing") : TEXT("legacy"),
                                   bTargetReady ? TEXT("MI_FX_TargetArc") : TEXT("legacy"), TargetOuterUU));
  return bRingReady || bTargetReady;
}

void FS08FieldMarks::SetFigureScale(float Scale) {
  FigureScale = Scale;
  if (UStaticMeshComponent* T = TargetRing.Get()) TargetBaseScale = T->GetRelativeScale3D();
  Apply();
}

double FS08FieldMarks::Now() const {
  const AActor* O = Owner.Get();
  const UWorld* World = O ? O->GetWorld() : nullptr;
  return World ? World->GetTimeSeconds() : 0.0;
}

bool FS08FieldMarks::SetSelected(bool bOn, bool bInstantOff) {
  if (!bRingReady) return bOn;
  if (!bOn && bInstantOff) {
    // FX-07 "перевыбор — сразу": another figure takes the selection, this ring goes in the same frame
    bRingOn = false;
    bRingAnim = false;
    RingPose = S08FieldFx::FMarkPose{1.0f, 0.0f, true};
    Apply();
    return false;
  }
  if (bOn != bRingOn) {
    bRingOn = bOn;
    bRingAnim = true;
    RingStartS = Now();
    Kick();
  }
  return bRingOn || bRingAnim;
}

bool FS08FieldMarks::SetTarget(bool bOn) {
  if (!bTargetReady) return bOn;
  if (bOn != bTargetOn) {
    bTargetOn = bOn;
    bTargetAnim = true;
    TargetStartS = Now();
    Kick();
  }
  return bTargetOn || bTargetAnim;
}

void FS08FieldMarks::HideNow() {
  bRingOn = bRingAnim = bTargetOn = bTargetAnim = false;
  RingPose = S08FieldFx::FMarkPose{1.0f, 0.0f, true};
  TargetPose = S08FieldFx::FMarkPose{1.0f, 0.0f, true};
  Apply();
}

void FS08FieldMarks::SetStatic(bool bRing, double RingMs, bool bTarget, double TargetMs) {
  if (bRingReady) {
    bRingOn = bRing;
    bRingAnim = false;
    RingPose = bRing ? S08FieldFx::SelectionAppear(RingMs, false) : S08FieldFx::FMarkPose{1.0f, 0.0f, true};
    if (UStaticMeshComponent* R = Ring.Get()) R->SetVisibility(bRing);
  }
  if (bTargetReady) {
    bTargetOn = bTarget;
    bTargetAnim = false;
    TargetPose = bTarget ? S08FieldFx::TargetAppear(TargetMs, false) : S08FieldFx::FMarkPose{1.0f, 0.0f, true};
    if (UStaticMeshComponent* T = TargetRing.Get()) T->SetVisibility(bTarget);
  }
  Apply();
}

void FS08FieldMarks::Kick() {
  Tick();
  AActor* O = Owner.Get();
  UWorld* World = O ? O->GetWorld() : nullptr;
  if (!World) return;
  FTimerManager& Timers = World->GetTimerManager();
  if (!bRingAnim && !bTargetAnim) {
    Timers.ClearTimer(Timer);
  } else if (!Timers.IsTimerActive(Timer)) {
    Timers.SetTimer(Timer, FTimerDelegate::CreateWeakLambda(O, [this] { Tick(); }), 1.0f / 60.0f, true);
  }
}

void FS08FieldMarks::Tick() {
  const bool bReduced = S08IconMotion::IsReducedMotion();
  const double NowS = Now();
  if (bRingAnim) {
    const double Ms = (NowS - RingStartS) * 1000.0;
    RingPose = bRingOn ? S08FieldFx::SelectionAppear(Ms, bReduced) : S08FieldFx::SelectionLeave(Ms, bReduced);
    if (RingPose.bDone) {
      bRingAnim = false;
      if (!bRingOn) {
        if (UStaticMeshComponent* R = Ring.Get()) R->SetVisibility(false);
      }
    }
  }
  if (bTargetAnim) {
    const double Ms = (NowS - TargetStartS) * 1000.0;
    TargetPose = bTargetOn ? S08FieldFx::TargetAppear(Ms, bReduced) : S08FieldFx::TargetLeave(Ms, bReduced);
    if (TargetPose.bDone) {
      bTargetAnim = false;
      if (!bTargetOn) {
        if (UStaticMeshComponent* T = TargetRing.Get()) T->SetVisibility(false);
      }
    }
  }
  Apply();
  if (!bRingAnim && !bTargetAnim) {
    if (AActor* O = Owner.Get()) {
      if (UWorld* World = O->GetWorld()) World->GetTimerManager().ClearTimer(Timer);
    }
  }
}

void FS08FieldMarks::Apply() {
  using namespace S08FieldFx;
  if (bRingReady) {
    if (UStaticMeshComponent* R = Ring.Get()) {
      const float S = SelectionPlaneUU / 100.0f * FigureScale;
      R->SetWorldScale3D(FVector(S, S, 1.0f));
      R->SetRelativeLocation(FVector(0.0f, 0.0f, SelectionZ));
    }
    if (UMaterialInstanceDynamic* M = RingMid.Get()) {
      M->SetScalarParameterValue(ParamScale, FigureScale * RingPose.Scale);
      M->SetScalarParameterValue(ParamOpacity, RingPose.Opacity);
    }
  }
  if (bTargetReady) {
    if (UStaticMeshComponent* T = TargetRing.Get()) {
      // the plane covers the arcs at the 1.15 appear scale; the SDF itself scales with the Scale parameter
      const float S = TargetPlaneUU / 100.0f * FigureScale * 1.15f;
      T->SetWorldScale3D(FVector(S, S, 1.0f));
      T->SetRelativeLocation(FVector(0.0f, 0.0f, TargetZ));
    }
    if (UMaterialInstanceDynamic* M = TargetMid.Get()) {
      M->SetScalarParameterValue(ParamScale, FigureScale * TargetPose.Scale);
      M->SetScalarParameterValue(ParamOpacity, TargetPose.Opacity);
    }
  }
}

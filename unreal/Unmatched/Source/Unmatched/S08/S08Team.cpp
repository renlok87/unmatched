#include "S08Team.h"

#include "S08FlowController.h"

bool S08ParseTeamColorMode(const FString& Text, ES08TeamColorMode& Out) {
  const FString T = Text.TrimStartAndEnd().ToLower();
  if (T.IsEmpty() || T == TEXT("absolute")) {
    Out = ES08TeamColorMode::Absolute;
    return true;
  }
  if (T == TEXT("relative")) {
    Out = ES08TeamColorMode::Relative;
    return true;
  }
  return false;
}

FString S08TeamP1OwnerId(const TArray<FS08RoomPlayer>& PlayersBySeat, const FString& HostId) {
  const FS08RoomPlayer* Best = nullptr;
  for (const FS08RoomPlayer& P : PlayersBySeat) {
    if (P.UserId.IsEmpty()) continue;
    if (!Best || P.SeatOrder < Best->SeatOrder) Best = &P;
  }
  if (Best) return Best->UserId;
  return HostId;
}

ES08TeamSlot S08TeamOf(const FString& FighterId, const FString& OwnerId, const FString& P1OwnerId) {
  if (!P1OwnerId.IsEmpty()) return OwnerId == P1OwnerId ? ES08TeamSlot::P1 : ES08TeamSlot::P2;
  return FighterId.StartsWith(TEXT("f-0-")) ? ES08TeamSlot::P1 : ES08TeamSlot::P2;
}

ES08TeamSlot S08TeamLook(ES08TeamSlot Team, bool bOwn, ES08TeamColorMode Mode) {
  if (Mode == ES08TeamColorMode::Relative) return bOwn ? ES08TeamSlot::P1 : ES08TeamSlot::P2;
  return Team;
}

namespace S08TeamPalette {
FLinearColor RingFill(ES08TeamSlot Slot) {
  return FLinearColor::FromSRGBColor(FColor::FromHex(Slot == ES08TeamSlot::P1 ? P1Hex : P2Hex));
}

FLinearColor Keyline() { return FLinearColor::FromSRGBColor(FColor::FromHex(KeylineHex)); }

FColor ChipColor(ES08TeamSlot Slot) {
  FColor C = FColor::FromHex(Slot == ES08TeamSlot::P1 ? P1ScreenHex : P2ScreenHex);
  C.A = 255;
  return C;
}
}  // namespace S08TeamPalette

namespace S08TeamRingSpec {
namespace {
constexpr int32 CircleSegments = 96;

void HexSideFrame(int32 K, FVector2D& N, FVector2D& T) {
  const double Phi = FMath::DegreesToRadians(60.0 * K + 30.0);
  N = FVector2D(FMath::Cos(Phi), FMath::Sin(Phi));
  T = FVector2D(-FMath::Sin(Phi), FMath::Cos(Phi));
}

/** One trimmed hexagon band quad per side (tools/art/t53_team_ring.py hex_band_quads). */
void HexBandQuads(float A0, float A1, TArray<TArray<FVector2D>>& Out) {
  const double Trim = (P2CornerGapUU * 0.5) / FMath::Sin(FMath::DegreesToRadians(60.0));
  const double Tan30 = FMath::Tan(FMath::DegreesToRadians(30.0));
  for (int32 K = 0; K < 6; ++K) {
    FVector2D N, T;
    HexSideFrame(K, N, T);
    const double H0 = A0 * Tan30 - Trim;
    const double H1 = A1 * Tan30 - Trim;
    Out.Add({N * A0 - T * H0, N * A1 - T * H1, N * A1 + T * H1, N * A0 + T * H0});
  }
}
}  // namespace

void OuterEdges(ES08TeamSlot Slot, TArray<TPair<FVector2D, FVector2D>>& OutSegments) {
  OutSegments.Reset();
  if (Slot == ES08TeamSlot::P1) {
    for (int32 I = 0; I < CircleSegments; ++I) {
      const double A0 = 2.0 * PI * I / CircleSegments;
      const double A1 = 2.0 * PI * (I + 1) / CircleSegments;
      OutSegments.Add({FVector2D(FMath::Cos(A0), FMath::Sin(A0)) * P1KeylineOut1,
                       FVector2D(FMath::Cos(A1), FMath::Sin(A1)) * P1KeylineOut1});
    }
    return;
  }
  TArray<TArray<FVector2D>> Quads;
  HexBandQuads(P2Fill1, P2KeylineOut1, Quads);
  for (const TArray<FVector2D>& Q : Quads) {
    OutSegments.Add({Q[1], Q[2]});  // the outer edge of the outer keyline quad
    OutSegments.Add({Q[0], Q[1]});  // gap end (the outer corner of the side)
    OutSegments.Add({Q[3], Q[2]});
  }
}

void FillQuads(ES08TeamSlot Slot, TArray<TArray<FVector2D>>& OutQuads) {
  OutQuads.Reset();
  if (Slot == ES08TeamSlot::P2) {
    HexBandQuads(P2Fill0, P2Fill1, OutQuads);
    return;
  }
  for (int32 I = 0; I < CircleSegments; ++I) {
    const double A0 = 2.0 * PI * I / CircleSegments;
    const double A1 = 2.0 * PI * (I + 1) / CircleSegments;
    const FVector2D D0(FMath::Cos(A0), FMath::Sin(A0));
    const FVector2D D1(FMath::Cos(A1), FMath::Sin(A1));
    OutQuads.Add({D0 * P1Fill0, D0 * P1Fill1, D1 * P1Fill1, D1 * P1Fill0});
  }
}
}  // namespace S08TeamRingSpec

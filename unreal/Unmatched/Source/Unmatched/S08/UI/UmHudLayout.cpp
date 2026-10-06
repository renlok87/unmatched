// VS-2 HB-06: the layout of the GAME screen - see UmHudLayout.h.
#include "UmHudLayout.h"

namespace UmHudLayout {
namespace {
// 04 §1.6 sizes (su). L = class L, S = class S; "Tall" = the 1080p column of L.
constexpr float GapSu = 8.0f;            // between stacked blocks
constexpr float HandGapLeftSu = 12.0f;   // PANEL-LOC -> hand corridor
constexpr float HandGapRightLSu = 12.0f; // hand corridor -> ACTIONS, class L (1080p 1540 = 1552 - 12)
constexpr float HandGapRightSSu = 8.0f;  // class S (1280 su: 1040 = 1048 - 8; HB-07 1137.8 su: 897.8)
constexpr float CaptionSu = 22.0f;       // "Рука {n}/{max}" over the row
constexpr float HandMinVisibleSu = 48.0f;  // the lowered hand (SD-26) - never less
constexpr float SubDefaultHSu = 40.0f;     // one type.body line in its capsule
constexpr float ToastDefaultHSu = 48.0f;
constexpr float SubMaxWSu = 720.0f;        // 04 §2.13
}  // namespace

const TCHAR* BlockName(EUmHudBlock Block) {
  switch (Block) {
    case EUmHudBlock::Top: return TEXT("top");
    case EUmHudBlock::Status: return TEXT("status");
    case EUmHudBlock::Center: return TEXT("center");
    case EUmHudBlock::Banner: return TEXT("banner");
    case EUmHudBlock::SourceSlot: return TEXT("slot");
    case EUmHudBlock::CombatL: return TEXT("combat.l");
    case EUmHudBlock::CombatR: return TEXT("combat.r");
    case EUmHudBlock::Defend: return TEXT("defend");
    case EUmHudBlock::Log: return TEXT("log");
    case EUmHudBlock::PanelLoc: return TEXT("panel.loc");
    case EUmHudBlock::PanelOpp: return TEXT("panel.opp");
    case EUmHudBlock::OppHand: return TEXT("opphand");
    case EUmHudBlock::Hand: return TEXT("hand");
    case EUmHudBlock::HandCaption: return TEXT("hand.caption");
    case EUmHudBlock::Toast: return TEXT("toast");
    case EUmHudBlock::Sub: return TEXT("sub");
    case EUmHudBlock::Decks: return TEXT("decks");
    case EUmHudBlock::DeckPanel: return TEXT("deckpanel");
    case EUmHudBlock::Actions: return TEXT("actions");
    default: return TEXT("?");
  }
}

FName FlagKey(EUmHudBlock Block) {
  switch (Block) {
    case EUmHudBlock::Center: return FName(TEXT("pending"));
    case EUmHudBlock::SourceSlot: return FName(TEXT("slot"));
    case EUmHudBlock::CombatL:
    case EUmHudBlock::CombatR:
    case EUmHudBlock::Defend: return FName(TEXT("combat"));
    case EUmHudBlock::PanelLoc:
    case EUmHudBlock::PanelOpp: return FName(TEXT("panels"));
    case EUmHudBlock::Hand:
    case EUmHudBlock::HandCaption: return FName(TEXT("hand"));
    default: return FName(BlockName(Block));
  }
}

bool IsPersistent(EUmHudBlock Block) {
  switch (Block) {
    case EUmHudBlock::Center:
    case EUmHudBlock::Banner:
    case EUmHudBlock::Toast:
    case EUmHudBlock::Sub:
    case EUmHudBlock::DeckPanel: return false;
    default: return Block != EUmHudBlock::Num;
  }
}
}  // namespace UmHudLayout

namespace {
FBox2D UmLayoutBox(float X, float Y, float W, float H) { return FBox2D(FVector2D(X, Y), FVector2D(X + W, Y + H)); }

double UmLayoutOverlap(const FBox2D& A, const FBox2D& B) {
  if (!A.bIsValid || !B.bIsValid) return 0.0;
  const double W = FMath::Min(A.Max.X, B.Max.X) - FMath::Max(A.Min.X, B.Min.X);
  const double H = FMath::Min(A.Max.Y, B.Max.Y) - FMath::Max(A.Min.Y, B.Min.Y);
  return W > 0.0 && H > 0.0 ? W * H : 0.0;
}

bool UmLayoutCrosses(const FBox2D& A, const TArray<FBox2D>& Avoid) {
  for (const FBox2D& B : Avoid) {
    if (UmLayoutOverlap(A, B) > 0.0) return true;
  }
  return false;
}
}  // namespace

FUmHudLayout FUmHudLayout::Compute(const FVector2D& InCanvasSu, float InPxPerSu, const FBox2D* InFieldSu) {
  using namespace UmHudLayout;
  FUmHudLayout L;
  L.CanvasSu = InCanvasSu;
  L.PxPerSu = InPxPerSu > 0.0f ? InPxPerSu : 1.0f;
  L.bClassS = InCanvasSu.X < ClassLMinWidthSu;
  L.bTall = InCanvasSu.Y >= TallMinHeightSu;
  L.MarginSu = L.bClassS ? 16.0f : 24.0f;
  if (InFieldSu && InFieldSu->bIsValid) {
    L.bHasField = true;
    L.FieldSu = *InFieldSu;
  }
  const float W = static_cast<float>(InCanvasSu.X);
  const float H = static_cast<float>(InCanvasSu.Y);
  const float M = L.MarginSu;
  auto Set = [&L](EUmHudBlock B, const FBox2D& R) { L.Rects[static_cast<int32>(B)] = R; };
  float CardMaxH = 208.0f;
  float HandGapRight = HandGapRightLSu;
  if (!L.bClassS) {
    const float StatusW = L.bTall ? 880.0f : 720.0f;
    const float CenterW = L.bTall ? 720.0f : 640.0f;
    const float CenterH = L.bTall ? 420.0f : 380.0f;
    Set(EUmHudBlock::Top, UmLayoutBox(M, M, 252.0f, 44.0f));
    Set(EUmHudBlock::Status, UmLayoutBox(0.5f * (W - StatusW), M, StatusW, 48.0f));
    Set(EUmHudBlock::Center, UmLayoutBox(0.5f * (W - CenterW), 80.0f, CenterW, CenterH));
    Set(EUmHudBlock::Banner, UmLayoutBox(0.5f * (W - 420.0f), 144.0f, 420.0f, 64.0f));
    Set(EUmHudBlock::SourceSlot, UmLayoutBox(M, 84.0f, 190.0f, 264.0f));
    // the card 230x319 and its role ribbon 230x28 under it (y 683)
    Set(EUmHudBlock::CombatL, UmLayoutBox(M, 360.0f, 230.0f, 351.0f));
    Set(EUmHudBlock::CombatR, UmLayoutBox(W - M - 230.0f, 360.0f, 230.0f, 351.0f));
    Set(EUmHudBlock::Defend, UmLayoutBox(M, 719.0f, 230.0f, 48.0f));
    const FBox2D PanelLoc = UmLayoutBox(M, H - M - 136.0f, 340.0f, 136.0f);
    Set(EUmHudBlock::PanelLoc, PanelLoc);
    Set(EUmHudBlock::PanelOpp, UmLayoutBox(W - M - 340.0f, M, 340.0f, 136.0f));
    // backs 48x67 + caption; 92 su high (HB-07 delta: the caption keeps 14 su from the edge at fractional DPI)
    Set(EUmHudBlock::OppHand, UmLayoutBox(W - M - 300.0f, M + 136.0f + GapSu, 300.0f, 92.0f));
    const FBox2D Actions = UmLayoutBox(W - M - 344.0f, H - M - 72.0f, 344.0f, 72.0f);
    Set(EUmHudBlock::Actions, Actions);
    const FBox2D Decks = UmLayoutBox(W - M - 288.0f, Actions.Min.Y - GapSu - 56.0f, 288.0f, 56.0f);
    Set(EUmHudBlock::Decks, Decks);
    const float LogH = L.bTall ? 200.0f : 104.0f;
    Set(EUmHudBlock::Log, UmLayoutBox(M, PanelLoc.Min.Y - GapSu - LogH, 300.0f, LogH));
    const float DeckW = L.bTall ? 380.0f : 340.0f;
    Set(EUmHudBlock::DeckPanel, UmLayoutBox(W - M - DeckW, 248.0f, DeckW, Decks.Min.Y - GapSu - 248.0f));
    L.HandLeftSu = PanelLoc.Max.X + HandGapLeftSu;
    L.HandRightSu = Actions.Min.X - HandGapRight;
  } else {
    CardMaxH = 166.0f;
    HandGapRight = HandGapRightSSu;
    Set(EUmHudBlock::Top, UmLayoutBox(M, M, 236.0f, 40.0f));
    Set(EUmHudBlock::Status, UmLayoutBox(0.5f * (W - 600.0f), M, 600.0f, 40.0f));
    Set(EUmHudBlock::Center, UmLayoutBox(0.5f * (W - 560.0f), 64.0f, 560.0f, 360.0f));
    Set(EUmHudBlock::Banner, UmLayoutBox(0.5f * (W - 420.0f), 112.0f, 420.0f, 64.0f));
    Set(EUmHudBlock::SourceSlot, UmLayoutBox(M, 64.0f, 120.0f, 166.0f));
    Set(EUmHudBlock::CombatL, UmLayoutBox(M, 240.0f, 150.0f, 232.0f));
    Set(EUmHudBlock::CombatR, UmLayoutBox(W - M - 150.0f, 240.0f, 150.0f, 232.0f));
    Set(EUmHudBlock::Defend, UmLayoutBox(M, 480.0f, 150.0f, 88.0f));  // two 40 su buttons, one per row
    const FBox2D PanelLoc = UmLayoutBox(M, H - M - 96.0f, 240.0f, 96.0f);
    Set(EUmHudBlock::PanelLoc, PanelLoc);
    Set(EUmHudBlock::PanelOpp, UmLayoutBox(W - M - 240.0f, M, 240.0f, 96.0f));
    Set(EUmHudBlock::OppHand, UmLayoutBox(W - M - 220.0f, M + 96.0f + GapSu, 220.0f, 87.0f));
    const FBox2D Actions = UmLayoutBox(W - M - 216.0f, H - M - 48.0f, 216.0f, 48.0f);
    Set(EUmHudBlock::Actions, Actions);
    const FBox2D Decks = UmLayoutBox(W - M - 136.0f, Actions.Min.Y - GapSu - 48.0f, 136.0f, 48.0f);
    Set(EUmHudBlock::Decks, Decks);
    // no LOG column in S: a pop-up list from TOP (ВР-H07)
    Set(EUmHudBlock::DeckPanel, UmLayoutBox(W - M - 300.0f, 168.0f, 300.0f, Decks.Min.Y - GapSu - 168.0f));
    L.HandLeftSu = PanelLoc.Max.X + HandGapLeftSu;
    L.HandRightSu = Actions.Min.X - HandGapRight;
  }
  // ВР-VS2-10: OPP-HAND (the backs of the opponent's hand) keeps out of FIELD - its width is the room right of the
  // cells (the step of the backs shrinks, 04 §2.3), never under 120 su. Sarpedon at 1137.8 su: 201 of 220.
  if (L.bHasField) {
    const FBox2D Opp = L.Rect(EUmHudBlock::OppHand);
    const float Room = W - M - (static_cast<float>(L.FieldSu.Max.X) + GapSu);
    const float OppW = FMath::Clamp(Room, 120.0f, static_cast<float>(Opp.Max.X - Opp.Min.X));
    Set(EUmHudBlock::OppHand, UmLayoutBox(W - M - OppW, static_cast<float>(Opp.Min.Y), OppW,
                                          static_cast<float>(Opp.Max.Y - Opp.Min.Y)));
  }
  // ВР-H02: the resting row starts 8 su + its caption under FIELD; without FIELD the full card height shows.
  const float CardTop = L.bHasField ? static_cast<float>(L.FieldSu.Max.Y) + GapSu + CaptionSu : H - CardMaxH;
  L.HandVisibleSu = FMath::Clamp(H - CardTop, HandMinVisibleSu, CardMaxH);
  const float HandTop = H - L.HandVisibleSu;
  const float HandW = FMath::Max(0.0f, L.HandRightSu - L.HandLeftSu);
  Set(EUmHudBlock::Hand, UmLayoutBox(L.HandLeftSu, HandTop, HandW, L.HandVisibleSu));
  Set(EUmHudBlock::HandCaption, UmLayoutBox(L.HandLeftSu, HandTop - CaptionSu, HandW, CaptionSu));
  // the default stack (no figure to avoid): the subtitle over the hand caption, the toasts over it
  {
    bool bTop = false;
    const TArray<FBox2D> None;
    const float ToastW = L.bClassS ? 440.0f : (L.bTall ? 560.0f : 520.0f);
    Set(EUmHudBlock::Toast, L.StackRect(EUmHudBlock::Toast, ToastW, ToastDefaultHSu, SubMaxWSu, SubDefaultHSu, None, bTop));
    Set(EUmHudBlock::Sub, L.StackRect(EUmHudBlock::Sub, ToastW, ToastDefaultHSu, SubMaxWSu, SubDefaultHSu, None, bTop));
  }
  // the gate: persistent blocks x FIELD (px^2)
  if (L.bHasField) {
    for (int32 I = 0; I < UmHudBlockCount; ++I) {
      const EUmHudBlock B = static_cast<EUmHudBlock>(I);
      if (!IsPersistent(B)) continue;
      L.OverlapFieldPx2 += UmLayoutOverlap(L.Rects[I], L.FieldSu) * L.PxPerSu * L.PxPerSu;
    }
  }
  return L;
}

FVector2D FUmHudLayout::DeckChipCentreSu() const {
  const FBox2D& D = Rect(EUmHudBlock::Decks);
  if (!D.bIsValid) return FVector2D::ZeroVector;
  // two chips side by side: the deck chip is the left half
  return FVector2D(D.Min.X + 0.25 * (D.Max.X - D.Min.X), 0.5 * (D.Min.Y + D.Max.Y));
}

FVector2D FUmHudLayout::DiscardChipCentreSu() const {
  const FBox2D& D = Rect(EUmHudBlock::Decks);
  if (!D.bIsValid) return FVector2D::ZeroVector;
  return FVector2D(D.Min.X + 0.75 * (D.Max.X - D.Min.X), 0.5 * (D.Min.Y + D.Max.Y));
}

FBox2D FUmHudLayout::StackRect(EUmHudBlock Which, float ToastWidthSu, float ToastHeightSu, float SubWidthSu,
                               float SubHeightSu, const TArray<FBox2D>& Avoid, bool& bOutTop, float HandTopSu) const {
  const float W = static_cast<float>(CanvasSu.X);
  const float MaxW = FMath::Max(0.0f, W - 2.0f * MarginSu);
  const float ToastW = FMath::Min(ToastWidthSu, MaxW);
  const float SubW = FMath::Min(FMath::Min(SubWidthSu, UmHudLayout::SubMaxWSu), MaxW);
  const float Gap = 8.0f;
  const FBox2D& Caption = Rect(EUmHudBlock::HandCaption);
  float Bottom = Caption.bIsValid ? static_cast<float>(Caption.Min.Y) - Gap : static_cast<float>(CanvasSu.Y) - MarginSu;
  if (HandTopSu >= 0.0f) Bottom = FMath::Min(Bottom, HandTopSu - Gap);
  // bottom: the subtitle right over the hand caption, the toasts over the subtitle (04 §2.13: "под стопкой тостов")
  const FBox2D SubBottom = UmLayoutBox(0.5f * (W - SubW), Bottom - SubHeightSu, SubW, SubHeightSu);
  const float ToastBottomEdge = SubHeightSu > 0.0f ? static_cast<float>(SubBottom.Min.Y) - Gap : Bottom;
  const FBox2D ToastBottom = UmLayoutBox(0.5f * (W - ToastW), ToastBottomEdge - ToastHeightSu, ToastW, ToastHeightSu);
  const bool bCross = (SubHeightSu > 0.0f && UmLayoutCrosses(SubBottom, Avoid)) ||
                      (ToastHeightSu > 0.0f && UmLayoutCrosses(ToastBottom, Avoid));
  bOutTop = bCross;
  if (!bCross) return Which == EUmHudBlock::Sub ? SubBottom : ToastBottom;
  // top strip (04 §2.12: centre, y 216 in L): the toasts first, the subtitle under them
  const float TopY = bClassS ? 144.0f : 216.0f;
  const FBox2D ToastTop = UmLayoutBox(0.5f * (W - ToastW), TopY, ToastW, ToastHeightSu);
  const float SubY = ToastHeightSu > 0.0f ? TopY + ToastHeightSu + Gap : TopY;
  const FBox2D SubTop = UmLayoutBox(0.5f * (W - SubW), SubY, SubW, SubHeightSu);
  return Which == EUmHudBlock::Sub ? SubTop : ToastTop;
}

float FUmHudLayout::EdgeRoomSu(bool bLeft) const {
  if (!bHasField) return bClassS ? 150.0f : 230.0f;
  const float Gap = 8.0f;
  const float Room = bLeft ? static_cast<float>(FieldSu.Min.X) - Gap - MarginSu
                           : static_cast<float>(CanvasSu.X) - MarginSu - (static_cast<float>(FieldSu.Max.X) + Gap);
  return FMath::Max(0.0f, Room);
}

FString FUmHudLayout::TraceLine(const FIntPoint& WindowPx) const {
  const FString Field = bHasField ? FString::Printf(TEXT("(%.0f,%.0f,%.0f,%.0f)"), FieldSu.Min.X, FieldSu.Min.Y,
                                                    FieldSu.Max.X - FieldSu.Min.X, FieldSu.Max.Y - FieldSu.Min.Y)
                                  : FString(TEXT("none"));
  // the blocks that cross FIELD (none when the gate holds)
  TArray<FString> Crossing;
  if (bHasField) {
    for (int32 I = 0; I < UmHudBlockCount; ++I) {
      const EUmHudBlock B = static_cast<EUmHudBlock>(I);
      if (UmHudLayout::IsPersistent(B) && UmLayoutOverlap(Rects[I], FieldSu) > 0.0) {
        Crossing.Add(UmHudLayout::BlockName(B));
      }
    }
  }
  return FString::Printf(
      TEXT("HUD-LAYOUT class=%s canvas=%.0fx%.0f scale=%.3f field=%s overlapField=%.0f window=%dx%d hand=%.0f..%.0f "
           "handVisible=%.0f crossing=%s"),
      bClassS ? TEXT("S") : TEXT("L"), CanvasSu.X, CanvasSu.Y, PxPerSu, *Field, OverlapFieldPx2, WindowPx.X, WindowPx.Y,
      HandLeftSu, HandRightSu, HandVisibleSu, Crossing.Num() ? *FString::Join(Crossing, TEXT(",")) : TEXT("-"));
}

namespace UmHudField {
bool Project(const FView& View, const FVector& World, FVector2D& OutPx) {
  const FRotationMatrix M(View.Rotation);
  const FVector Forward = M.GetUnitAxis(EAxis::X);
  const FVector Right = M.GetUnitAxis(EAxis::Y);
  const FVector Up = M.GetUnitAxis(EAxis::Z);
  const FVector D = World - View.Location;
  const double Depth = FVector::DotProduct(D, Forward);
  if (Depth <= KINDA_SMALL_NUMBER || View.ViewportPx.X <= 0.0 || View.ViewportPx.Y <= 0.0) return false;
  // AspectRatio_MaintainXFOV (the LocalPlayer default): the horizontal FOV is the camera's, the vertical follows.
  const double HalfTanH = FMath::Tan(FMath::DegreesToRadians(0.5 * View.HFovDeg));
  const double HalfTanV = HalfTanH * View.ViewportPx.Y / View.ViewportPx.X;
  const double NdcX = FVector::DotProduct(D, Right) / (Depth * HalfTanH);
  const double NdcY = FVector::DotProduct(D, Up) / (Depth * HalfTanV);
  OutPx = FVector2D((0.5 + 0.5 * NdcX) * View.ViewportPx.X, (0.5 - 0.5 * NdcY) * View.ViewportPx.Y);
  return true;
}

FBox2D CellsEnvelopePx(const FView& View, const TArray<FVector>& Centres, float RadiusUU) {
  FBox2D Out(ForceInit);
  for (const FVector& C : Centres) {
    for (int32 K = 0; K < 8; ++K) {
      const double A = UE_DOUBLE_PI * 0.25 * K;
      const FVector P = C + FVector(FMath::Cos(A) * RadiusUU, FMath::Sin(A) * RadiusUU, 0.0);
      FVector2D Px;
      if (Project(View, P, Px)) Out += Px;
    }
  }
  return Out;
}
}  // namespace UmHudField

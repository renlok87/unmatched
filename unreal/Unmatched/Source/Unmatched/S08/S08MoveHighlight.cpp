#include "S08MoveHighlight.h"
#include "Fx/S08FieldFx.h"
#include "S08HudTokens.generated.h"
#include "S08IconMotion.h"
#include "S08Render.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

namespace {
TOptional<bool> GPlatesOverride;

/** Picks the higher-priority state of a channel (lower non-zero enum value wins; None never wins). */
template <typename TEnum>
void Raise(TEnum& InOut, TEnum Candidate) {
  if (Candidate == TEnum::None) return;
  if (InOut == TEnum::None || static_cast<uint8>(Candidate) < static_cast<uint8>(InOut)) InOut = Candidate;
}

uint32 HashFloat(uint32 H, float V) { return HashCombineFast(H, GetTypeHash(V)); }
}  // namespace

const FS08PlateView* FS08MoveDraftView::Find(int32 X, int32 Y) const {
  for (const FS08PlateView& P : Plates) {
    if (P.X == X && P.Y == Y) return &P;
  }
  return nullptr;
}

namespace S08MoveHighlight {

bool PlatesEnabled() {
  if (GPlatesOverride.IsSet()) return GPlatesOverride.GetValue();
  static const bool bFlag = FParse::Param(FCommandLine::Get(), TEXT("S08MovePlates"));
  return bFlag;
}

void SetEnabledOverrideForTest(TOptional<bool> bEnabled) { GPlatesOverride = bEnabled; }

const TCHAR* RingStateName(ES08RingState State) {
  switch (State) {
    case ES08RingState::Conflict: return TEXT("conflict");
    case ES08RingState::NeedBoost: return TEXT("needBoost");
    case ES08RingState::Destination: return TEXT("destination");
    case ES08RingState::Sent: return TEXT("sent");
    case ES08RingState::EnemyBlock: return TEXT("enemyBlock");
    case ES08RingState::AllyPass: return TEXT("allyPass");
    case ES08RingState::ReachBase: return TEXT("reachBase");
    case ES08RingState::ReachBoost: return TEXT("reachBoost");
    case ES08RingState::PendingMove: return TEXT("pendingMove");
    case ES08RingState::PendingPlace: return TEXT("pendingPlace");
    case ES08RingState::Candidate: return TEXT("candidate");
    default: return TEXT("none");
  }
}

const TCHAR* OutlineStateName(ES08OutlineState State) {
  switch (State) {
    case ES08OutlineState::Threat: return TEXT("threat");
    case ES08OutlineState::LastTo: return TEXT("lastTo");
    case ES08OutlineState::LastFrom: return TEXT("lastFrom");
    default: return TEXT("none");
  }
}

const TCHAR* GlyphStateName(ES08GlyphState State) {
  switch (State) {
    case ES08GlyphState::Invalid: return TEXT("invalid");
    case ES08GlyphState::Conflict: return TEXT("conflict");
    case ES08GlyphState::Order: return TEXT("order");
    case ES08GlyphState::Step: return TEXT("step");
    case ES08GlyphState::Hint: return TEXT("hint");
    default: return TEXT("none");
  }
}

namespace {
/** Space flags from the current positions: a living figure (Occupied) and a hero's leader pip. */
void ApplyFighterFlags(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters, bool bLeaderPips,
                       TMap<uint64, FS08PlateView>& Spaces) {
  for (const FS08BoardFighter& F : Fighters) {
    if (!F.IsAlive() || !Board.IsBoardSpace(F.X, F.Y)) continue;
    if (FS08PlateView* P = Spaces.Find(FS08BoardModel::CellKey(F.X, F.Y))) {
      P->Flags |= S08PlateFlags::Occupied;
      if (bLeaderPips && F.bIsHero) P->Flags |= S08PlateFlags::LeaderPip;
    }
  }
}

FS08MoveDraftView Finish(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters, bool bLeaderPips,
                         TMap<uint64, FS08PlateView>& Spaces, const FString& Source) {
  ApplyFighterFlags(Board, Fighters, bLeaderPips, Spaces);
  FS08MoveDraftView View;
  View.Source = Source;
  for (TPair<uint64, FS08PlateView>& Pair : Spaces) {
    const FS08PlateView& P = Pair.Value;
    // a space whose only data are the figure flags shows nothing
    if (P.Ring == ES08RingState::None && P.Outline == ES08OutlineState::None && !P.bPathDot &&
        P.Glyph == ES08GlyphState::None) {
      continue;
    }
    View.Plates.Add(P);
  }
  View.Plates.Sort([](const FS08PlateView& A, const FS08PlateView& B) { return A.Y != B.Y ? A.Y < B.Y : A.X < B.X; });
  View.Revision = ViewHash(View);
  return View;
}
}  // namespace

FS08MoveDraftView BuildDraftView(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                 const FS08MoveDraftInput& Input) {
  TMap<uint64, FS08PlateView> Spaces;
  // every board space gets a record (the figure flags need them); the empty ones are dropped in Finish
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (!Board.IsBoardSpace(X, Y)) continue;
      FS08PlateView P;
      P.X = X;
      P.Y = Y;
      Spaces.Add(FS08BoardModel::CellKey(X, Y), P);
    }
  }
  auto At = [&](const FIntPoint& C) -> FS08PlateView* { return Spaces.Find(FS08BoardModel::CellKey(C.X, C.Y)); };

  // V-01 / V-02: the tiers of the selected fighter (its own space never gets a plate)
  if (!Input.SelectedFighterId.IsEmpty()) {
    for (const FIntPoint& C : Input.BaseTier) {
      if (C == Input.SelectedStart) continue;
      if (FS08PlateView* P = At(C)) Raise(P->Ring, ES08RingState::ReachBase);
    }
    for (const TPair<FIntPoint, int32>& C : Input.BoostTier) {
      if (C.Key == Input.SelectedStart) continue;
      if (FS08PlateView* P = At(C.Key)) {
        const ES08RingState Before = P->Ring;
        Raise(P->Ring, ES08RingState::ReachBoost);
        if (P->Ring == ES08RingState::ReachBoost && Before != ES08RingState::ReachBoost) P->Chip = C.Value;
      }
    }
    // V-06 / V-07: allies and enemies within the graph range of the selected fighter
    const FS08BoardFighter* Mover = nullptr;
    for (const FS08BoardFighter& F : Fighters) {
      if (F.Id == Input.SelectedFighterId) Mover = &F;
    }
    if (Mover && Input.SelectedStart.X >= 0) {
      for (const FS08BoardFighter& F : Fighters) {
        if (F.Id == Mover->Id || !F.IsAliveBlocker() || F.X < 0) continue;
        const int32 Dist = Board.GraphDistance(Input.SelectedStart, FIntPoint(F.X, F.Y));
        if (Dist == MAX_int32 || Dist > Input.MarkRange) continue;
        if (FS08PlateView* P = At(FIntPoint(F.X, F.Y))) {
          Raise(P->Ring, F.OwnerId == Mover->OwnerId ? ES08RingState::AllyPass : ES08RingState::EnemyBlock);
        }
      }
    }
  }
  // V-03 / V-04 / V-04b / V-09 / V-10: the drafted moves (every move at once, MS-R-13)
  for (const FS08MoveDraftInput::FMove& Move : Input.Moves) {
    for (int32 I = 0; I + 1 < Move.Path.Num(); ++I) {
      if (FS08PlateView* P = At(Move.Path[I])) P->bPathDot = true;
    }
    FS08PlateView* Dest = At(Move.Dest);
    if (!Dest) continue;
    ES08RingState Ring = ES08RingState::Destination;
    if (Move.Status == FS08MoveDraftInput::EMoveStatus::Conflict) {
      Ring = ES08RingState::Conflict;
      Raise(Dest->Glyph, ES08GlyphState::Conflict);
    } else if (Move.Status == FS08MoveDraftInput::EMoveStatus::NeedBoost) {
      Ring = ES08RingState::NeedBoost;
    } else if (Input.bSent) {
      Ring = ES08RingState::Sent;
    }
    const ES08RingState Before = Dest->Ring;
    Raise(Dest->Ring, Ring);
    if (Dest->Ring == ES08RingState::NeedBoost && Before != ES08RingState::NeedBoost) Dest->Chip = Move.RequiredBoost;
    if (Dest->Order == 0 || Move.Order + 1 < Dest->Order) Dest->Order = Move.Order + 1;
    Dest->Steps = Move.Path.Num();
    Raise(Dest->Glyph, ES08GlyphState::Order);
    if (Input.bSent) Dest->Flags |= S08PlateFlags::Sent;
  }
  // V-11 / V-12: a pending MOVE / PLACE head of this viewer
  if (Input.bPending) {
    for (const uint64 Key : Input.PendingCells) {
      if (FS08PlateView* P = Spaces.Find(Key)) {
        Raise(P->Ring, Input.bPendingPlace ? ES08RingState::PendingPlace : ES08RingState::PendingMove);
      }
    }
  }
  // V-17: candidate rings under the own fighters that may move (DE-017: S09MoveDraftView::BuildInput, MS-S-06)
  for (const FString& Id : Input.CandidateFighterIds) {
    for (const FS08BoardFighter& F : Fighters) {
      if (F.Id != Id || !F.IsAlive()) continue;
      if (FS08PlateView* P = At(FIntPoint(F.X, F.Y))) {
        Raise(P->Ring, ES08RingState::Candidate);
        P->FigureScale = F.bIsHero ? 1.0f : S08TeamRingSpec::SidekickScale;
      }
    }
  }
  // V-14 / V-15 (MS-T-17): the last move - starts, path points, ends; a space that is both an end and a start (a chain
  // of moves, a return to the start) is an end (LastTo > LastFrom)
  // VS-6 FX-14 (ВР-29): by default the last move is the dashed path + arrow (View.LastPaths below); the MS-T-17
  // outlines and dots only with -S08LastMoveLegacy
  const bool bLastPaths = Input.LastMove.IsSet() && !S08FieldFx::LastMoveLegacy();
  if (Input.LastMove.IsSet() && !bLastPaths) {
    for (const FIntPoint& C : Input.LastMove.From) {
      if (FS08PlateView* P = At(C)) Raise(P->Outline, ES08OutlineState::LastFrom);
    }
    for (const FIntPoint& C : Input.LastMove.To) {
      if (FS08PlateView* P = At(C)) Raise(P->Outline, ES08OutlineState::LastTo);
    }
    for (const FIntPoint& C : Input.LastMove.Dots) {
      if (FS08PlateView* P = At(C)) P->bPathDot = true;
    }
    for (TPair<uint64, FS08PlateView>& Pair : Spaces) {
      FS08PlateView& P = Pair.Value;
      if (P.Outline == ES08OutlineState::LastTo || P.Outline == ES08OutlineState::LastFrom) {
        P.OutlineColor = Input.LastMove.Color;
      }
    }
  }
  if (FS08PlateView* P = At(Input.Hover)) P->Flags |= S08PlateFlags::Hover;
  FS08MoveDraftView View = Finish(Board, Fighters, Input.bLeaderPips, Spaces, Input.Source);
  View.Hover = Input.Hover;
  if (bLastPaths) {
    for (int32 I = 0; I < Input.LastMove.Paths.Num(); ++I) {
      FS08LastPathView Path;
      Path.Cells = Input.LastMove.Paths[I];
      Path.bPlace = Input.LastMove.Places.IsValidIndex(I) && Input.LastMove.Places[I];
      Path.Color = Input.LastMove.Color;
      if (Path.Cells.Num() >= 2) View.LastPaths.Add(MoveTemp(Path));
    }
  }
  // the paths (drawn as a line by MS-T-09; the centre dots above already mark their spaces)
  for (const FS08MoveDraftInput::FMove& Move : Input.Moves) {
    FS08PathView Path;
    Path.FighterId = Move.FighterId;
    Path.Order = Move.Order;
    Path.Cells.Add(Move.Start);
    Path.Cells.Append(Move.Path);
    Path.bConflict = Move.Status == FS08MoveDraftInput::EMoveStatus::Conflict;
    Path.bNeedBoost = Move.Status == FS08MoveDraftInput::EMoveStatus::NeedBoost;
    Path.bSent = Input.bSent;
    View.Paths.Add(MoveTemp(Path));
  }
  View.Revision = ViewHash(View);
  return View;
}

FS08MoveDraftView ViewFromReachable(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                    const FString& FighterId, const TSet<uint64>& Reachable, bool bLeaderPips) {
  TMap<uint64, FS08PlateView> Spaces;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (!Board.IsBoardSpace(X, Y)) continue;
      FS08PlateView P;
      P.X = X;
      P.Y = Y;
      Spaces.Add(FS08BoardModel::CellKey(X, Y), P);
    }
  }
  FIntPoint Own(-1, -1);
  for (const FS08BoardFighter& F : Fighters) {
    if (F.Id == FighterId) Own = FIntPoint(F.X, F.Y);
  }
  if (!FighterId.IsEmpty()) {
    for (const uint64 Key : Reachable) {
      if (Key == FS08BoardModel::CellKey(Own.X, Own.Y)) continue;
      if (FS08PlateView* P = Spaces.Find(Key)) Raise(P->Ring, ES08RingState::ReachBase);
    }
  }
  return Finish(Board, Fighters, bLeaderPips, Spaces, FighterId.IsEmpty() ? TEXT("none") : TEXT("reach"));
}

uint32 ViewHash(const FS08MoveDraftView& View) {
  uint32 H = 0x9E3779B9u;
  for (const FS08PlateView& P : View.Plates) {
    H = HashCombineFast(H, GetTypeHash(P.X));
    H = HashCombineFast(H, GetTypeHash(P.Y));
    H = HashCombineFast(H, static_cast<uint32>(P.Ring) | (static_cast<uint32>(P.Outline) << 8) |
                               (static_cast<uint32>(P.Glyph) << 16) | (P.bPathDot ? 1u << 24 : 0u));
    H = HashCombineFast(H, GetTypeHash(P.Steps) ^ (GetTypeHash(P.Chip) << 1) ^ (GetTypeHash(P.Order) << 2));
    H = HashCombineFast(H, static_cast<uint32>(P.Flags) | (static_cast<uint32>(P.OutlineColor) << 8));
    H = HashFloat(H, P.FigureScale);
  }
  for (const FS08PathView& Path : View.Paths) {
    H = HashCombineFast(H, GetTypeHash(Path.FighterId));
    for (const FIntPoint& C : Path.Cells) H = HashCombineFast(H, GetTypeHash(C));
    H = HashCombineFast(H, (Path.bConflict ? 1u : 0u) | (Path.bNeedBoost ? 2u : 0u) | (Path.bSent ? 4u : 0u));
  }
  for (const FS08LastPathView& Path : View.LastPaths) {
    for (const FIntPoint& C : Path.Cells) H = HashCombineFast(H, GetTypeHash(C));
    H = HashCombineFast(H, (Path.bPlace ? 1u : 0u) | (static_cast<uint32>(Path.Color) << 1) | 0x80000000u);
  }
  H = HashCombineFast(H, GetTypeHash(View.Hover));
  return H;
}

FString FGeometryCheck::TraceLine(const FString& Source) const {
  return FString::Printf(
      TEXT("MS-HL geom style=%s ring=%.2f..%.2f inBand=%d outline=%.2f..%.2f outlineOk=%d occupiedClear=%.2f clearOk=%d ")
      TEXT("pipCut=%.1f pipHalf=%.1f pipClear=%d ok=%d"),
      *Source, RingBandInner, RingBandOuter, bRingInBand ? 1 : 0, OutlineInner, OutlineOuter, bOutlineInBand ? 1 : 0,
      OccupiedClear, bOccupiedClear ? 1 : 0, PipCutDeg, PipHalfAngleDeg, bPipClear ? 1 : 0, Ok() ? 1 : 0);
}

FGeometryCheck CheckGeometry(const FS08MoveSelectionSpec& Spec) {
  FGeometryCheck G;
  G.RingBandInner = Spec.RingBandInnerUU();
  G.RingBandOuter = Spec.RingBandOuterUU();
  G.OutlineInner = Spec.OutlineInnerUU;
  G.OutlineOuter = Spec.OutlineOuterUU;
  G.OccupiedClear = Spec.OccupiedClearUU;
  G.PipCutDeg = Spec.PipCutDeg;
  const float Tol = 1e-3f;
  G.bRingInBand = G.RingBandInner >= 30.0f - Tol && G.RingBandOuter <= 40.0f + Tol;
  G.bOutlineInBand = G.OutlineInner >= 39.6f - Tol && G.OutlineOuter <= 41.0f + Tol && G.OutlineInner >= G.RingBandOuter - Tol;
  // nothing of the plate inside r 30 on an occupied space: the clear circle covers r 30 and the ring band starts outside
  G.bOccupiedClear = G.OccupiedClear >= 30.0f - Tol && G.RingBandInner >= G.OccupiedClear - Tol;
  // the leader pip of a hero (S08LeaderPipTransforms at ring scale 1): a diamond (with its keyline) centred on +Y at
  // P1RimOut1 + gap; at every radius of the ring band and the outline its half width seen from the centre must be
  // inside the cut, so the ring and the outline never cross it
  {
    using namespace S08MapSurfaceSpec;
    const float Centre = S08TeamRingSpec::P1RimOut1 + LeaderPipGapUU;
    const float HalfDiag = (LeaderPipSizeUU + 2.0f * LeaderPipKeylineUU) * UE_INV_SQRT_2;
    float Worst = 0.0f;
    const float From = FMath::Min(G.RingBandInner, G.OccupiedClear);
    const float To = FMath::Max(G.RingBandOuter, G.OutlineOuter);
    for (int32 I = 0; I <= 200; ++I) {
      const float R = FMath::Lerp(From, To, I / 200.0f);
      const float HalfWidth = HalfDiag - FMath::Abs(R - Centre);
      if (HalfWidth <= 0.0f || R <= 0.0f) continue;
      Worst = FMath::Max(Worst, FMath::RadiansToDegrees(FMath::Atan2(HalfWidth, R)));
    }
    G.PipHalfAngleDeg = Worst;
    G.bPipClear = Worst <= G.PipCutDeg + Tol;
  }
  return G;
}

}  // namespace S08MoveHighlight

const TCHAR* S08MovePlateSpec::ChannelName(EChannel Channel) {
  switch (Channel) {
    case EChannel::Fill: return TEXT("PlateFill");
    case EChannel::Ring: return TEXT("PlateRing");
    case EChannel::Outline: return TEXT("PlateOutline");
    case EChannel::Glyph: return TEXT("Glyphs");
    default: return TEXT("?");
  }
}

// ---------------------------------------------------------------------------------------------------- component

US08MoveHighlightComponent::US08MoveHighlightComponent() { PrimaryComponentTick.bCanEverTick = false; }

void US08MoveHighlightComponent::EnsurePlates() {
  if (Plates) return;
  // MS-AT-41: ONE primitive for every channel - one translucency draw and one occlusion query (the engine has no
  // per-component switch for occlusion queries; four ISMs cost +8 draw calls). One material slot (the engine plane has
  // one section and one LOD), no shadow, no decals, no navigation.
  Plates = NewObject<UInstancedStaticMeshComponent>(GetOwner() ? static_cast<UObject*>(GetOwner()) : this,
                                                    FName(TEXT("MoveHL_Plates")));
  Plates->SetupAttachment(this);
  Plates->SetStaticMesh(PlaneMesh);
  Plates->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  Plates->SetCanEverAffectNavigation(false);
  Plates->SetNumCustomDataFloats(S08MovePlateSpec::NumCustomData);
  // the game layer over the board; inside the ISM the layers keep fill < ring < outline < glyph by the channel-major
  // instance order (a translucent ISM preserves it: FMeshBatchElement::bPreserveInstanceOrder)
  Plates->SetTranslucentSortPriority(10);
  Plates->SetCastShadow(false);
  Plates->SetReceivesDecals(false);
  S08ApplyGameLayerPrimitive(Plates);
  if (IsRegistered()) Plates->RegisterComponent();
}

void US08MoveHighlightComponent::Initialize(UStaticMesh* Plane) {
  if (bInitialized) return;
  bInitialized = true;
  PlaneMesh = Plane;
  PlateMaterial = LoadObject<UMaterialInterface>(nullptr, S08MovePlateSpec::MaterialPath, nullptr, LOAD_NoWarn);
  EnsurePlates();
  PlateMid = nullptr;
  if (PlateMaterial && PlaneMesh) {
    PlateMid = UMaterialInstanceDynamic::Create(PlateMaterial, this);
    Plates->SetMaterial(0, PlateMid);
    MaterialName = PlateMaterial->GetName();
    bReady = true;
  }
  // 04 §6.1 / MS-R-74: the trace names the material actually used; a missing one is a gate error (never the default
  // material on a plate) - the board keeps the old ring then
  FS08Trace::Write(FString::Printf(TEXT("MS-HL assets plate=%s path=- ghost=- plane=%s ready=%d%s"),
                                   PlateMaterial ? *PlateMaterial->GetName() : TEXT("missing"),
                                   PlaneMesh ? *PlaneMesh->GetName() : TEXT("missing"), bReady ? 1 : 0,
                                   bReady ? TEXT("") : TEXT(" fallback=legacy-ring")));
}

void US08MoveHighlightComponent::ApplyStyle(const FS08MoveSelectionSpec& InStyle) {
  Style = InStyle;
  using namespace S08MovePlateSpec;
  UMaterialInstanceDynamic* Mid = PlateMid;
  if (!Mid) return;
  Mid->SetScalarParameterValue(ParamShape, bSquare ? 1.0f : 0.0f);
  Mid->SetScalarParameterValue(ParamHalfUU, HalfUU);
  Mid->SetScalarParameterValue(ParamRingCenter, Style.RingCenterUU);
  Mid->SetScalarParameterValue(ParamRingWidth, Style.RingWidthUU);
  Mid->SetScalarParameterValue(ParamKeyline, Style.KeylineUU);
  Mid->SetScalarParameterValue(ParamOutlineInner, Style.OutlineInnerUU);
  Mid->SetScalarParameterValue(ParamOutlineOuter, Style.OutlineOuterUU);
  Mid->SetScalarParameterValue(ParamOccClear, Style.OccupiedClearUU);
  Mid->SetScalarParameterValue(ParamPipCutDeg, Style.PipCutDeg);
  Mid->SetScalarParameterValue(ParamFillAlpha, Style.FillAlpha);
  Mid->SetScalarParameterValue(ParamDashCount, static_cast<float>(Style.DashCount));
  Mid->SetScalarParameterValue(ParamDashDuty, Style.DashDuty);
  Mid->SetScalarParameterValue(ParamCandRadius, Style.CandidateRadiusUU);
  Mid->SetScalarParameterValue(ParamCandWidth, Style.CandidateWidthUU);
  Mid->SetScalarParameterValue(ParamCandAlpha, Style.CandidateAlpha);
  Mid->SetScalarParameterValue(ParamLastMoveAlpha, Style.LastMoveAlpha);
  Mid->SetScalarParameterValue(ParamLastMoveFade, LastMoveFade);
  // sRGB bytes of the profile -> linear (the W4-B colour rule, FLinearColor::FromSRGBColor)
  Mid->SetVectorParameterValue(ParamPlateColor, FLinearColor::FromSRGBColor(Style.PlateColor));
  Mid->SetVectorParameterValue(ParamKeylineColor, FLinearColor::FromSRGBColor(Style.KeylineColor));
  Mid->SetVectorParameterValue(ParamErrorColor, FLinearColor::FromSRGBColor(Style.InvalidColor));
  Mid->SetVectorParameterValue(ParamTeamP1Color, FLinearColor::FromSRGBColor(TeamP1Screen));
  Mid->SetVectorParameterValue(ParamTeamP2Color, FLinearColor::FromSRGBColor(TeamP2Screen));
  // VS-6 FX-08 / FX-09: board.choice of the profile (= the token, ВР-76) and board.target of the pulse on a target
  Mid->SetVectorParameterValue(ParamChoiceColor, FLinearColor::FromSRGBColor(Style.ChoiceColor));
  Mid->SetVectorParameterValue(ParamTargetColor, FLinearColor::FromSRGBColor(S08HudTokens::Color_BoardTarget));
  Mid->SetScalarParameterValue(ParamCandFade, 1.0f);
  Mid->SetScalarParameterValue(ParamCandLeave, 1.0f);
  Mid->SetScalarParameterValue(ParamPendFade, 1.0f);
}

void US08MoveHighlightComponent::BuildForBoard(const FS08BoardModel& InBoard, const FS08MoveSelectionSpec& InStyle) {
  EnsurePlates();
  ++BuildCount;
  Board = InBoard;
  bSquare = !InBoard.bHasTopology;
  SpaceCells.Reset();
  InstanceByCell.Reset();
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (!Board.IsBoardSpace(X, Y)) continue;
      InstanceByCell.Add(FS08BoardModel::CellKey(X, Y), SpaceCells.Num());
      SpaceCells.Add(FIntPoint(X, Y));
    }
  }
  const int32 NumChannels = static_cast<int32>(S08MovePlateSpec::EChannel::Count);
  Written.SetNum(NumChannels);
  WrittenZ.SetNum(NumChannels);
  Plates->ClearInstances();
  TArray<FTransform> Hidden;
  Hidden.Reserve(SpaceCells.Num() * NumChannels);
  for (int32 C = 0; C < NumChannels; ++C) {
    for (const FIntPoint& Cell : SpaceCells) {
      Hidden.Add(FTransform(FRotator::ZeroRotator, Board.CellToWorld(Cell.X, Cell.Y), FVector::ZeroVector));
    }
    Written[C].Init(TArray<float>(), SpaceCells.Num());
    for (TArray<float>& Data : Written[C]) {
      Data.Init(0.0f, S08MovePlateSpec::NumCustomData);
      Data[S08MovePlateCpd::Channel] = static_cast<float>(C);
    }
    WrittenZ[C].Init(-1e6f, SpaceCells.Num());
  }
  // VS-6: the FX-14 dash quads and arrowheads and the FX-09 pulse after the per-space channels (drawn on top)
  const int32 Extra = S08MovePlateSpec::PathSlots + S08MovePlateSpec::ArrowSlots + S08MovePlateSpec::PulseSlots;
  for (int32 I = 0; I < Extra; ++I) Hidden.Add(FTransform(FRotator::ZeroRotator, FVector::ZeroVector, FVector::ZeroVector));
  Plates->AddInstances(Hidden, false);
  // the channel of every instance is written once here and never changes
  for (int32 C = 0; C < NumChannels; ++C) {
    for (int32 I = 0; I < SpaceCells.Num(); ++I) {
      Plates->SetCustomDataValue(C * SpaceCells.Num() + I, S08MovePlateCpd::Channel, static_cast<float>(C), false);
    }
  }
  for (int32 I = 0; I < Extra; ++I) {
    const float Ch = I < S08MovePlateSpec::PathSlots ? S08MovePlateSpec::PathChannel
                     : I < S08MovePlateSpec::PathSlots + S08MovePlateSpec::ArrowSlots ? S08MovePlateSpec::ArrowChannel
                                                                                        : S08MovePlateSpec::PulseChannel;
    Plates->SetCustomDataValue(ExtraInstance(I), S08MovePlateCpd::Channel, Ch, false);
  }
  PrevCandidates.Reset();
  PrevPending.Reset();
  PrevCandidateScale.Reset();
  Leaving.Reset();
  bPulseOn = false;
  Plates->MarkRenderStateDirty();
  AppliedHash = 0;
  ApplyStyle(InStyle);
  FS08Trace::Write(FString::Printf(TEXT("MS-HL build n=%d spaces=%d channels=%d isms=1 instances=%d shape=%s style=%s plate=%s path=%s ready=%d"),
                                   BuildCount, SpaceCells.Num(), NumChannels, Plates->GetInstanceCount(),
                                   bSquare ? TEXT("square") : TEXT("circle"), *Style.Source, *S08ColorHex(Style.PlateColor),
                                   *S08ColorHex(Style.PathColor), bReady ? 1 : 0));
  FS08Trace::Write(S08MoveHighlight::CheckGeometry(Style).TraceLine(Style.Source));
}

void US08MoveHighlightComponent::WriteInstance(S08MovePlateSpec::EChannel Channel, int32 Space,
                                               const float (&Data)[S08MovePlateSpec::NumCustomData], bool bShow,
                                               float Z) {
  const int32 C = static_cast<int32>(Channel);
  const int32 Instance = IsmInstance(Channel, Space);
  for (int32 Slot = 0; Slot < S08MovePlateSpec::NumCustomData; ++Slot) {
    Plates->SetCustomDataValue(Instance, Slot, Data[Slot], false);
    Written[C][Space][Slot] = Data[Slot];
  }
  const FIntPoint Cell = SpaceCells[Space];
  const float Scale = bShow ? S08MovePlateSpec::HalfUU * 2.0f / 100.0f : 0.0f;
  const FVector Location = Board.CellToWorld(Cell.X, Cell.Y) + FVector(0.0f, 0.0f, Z);
  Plates->UpdateInstanceTransform(Instance, FTransform(FRotator::ZeroRotator, Location, FVector(Scale, Scale, bShow ? 1.0f : 0.0f)),
                                  false, false, true);
  WrittenZ[C][Space] = bShow ? Z : -1e6f;
}

void US08MoveHighlightComponent::SetLastMoveFade(float Fade) {
  Fade = FMath::Clamp(Fade, 0.0f, 1.0f);
  if (FMath::IsNearlyEqual(Fade, LastMoveFade, 1.0e-3f)) return;
  LastMoveFade = Fade;
  // one MID: only the outline channel reads LastMoveFade (M_UM_MovePlate), the other channels do not change
  if (PlateMid) PlateMid->SetScalarParameterValue(S08MovePlateSpec::ParamLastMoveFade, LastMoveFade);
}

int32 US08MoveHighlightComponent::ApplyView(const FS08MoveDraftView& InView) {
  if (!Plates || SpaceCells.Num() == 0) return 0;
  FS08MoveDraftView View = InView;
  if (bChoiceOnly) {
    // VS-6: without -S08MovePlates only the choice layer - the V-17 rings (DE-017), the FX-14 path, the pulse
    TArray<FS08PlateView> Kept;
    for (const FS08PlateView& P : View.Plates) {
      if (P.Ring != ES08RingState::Candidate) continue;
      FS08PlateView C = P;
      C.Outline = ES08OutlineState::None;
      C.bPathDot = false;
      C.Glyph = ES08GlyphState::None;
      C.Steps = C.Chip = C.Order = 0;
      Kept.Add(C);
    }
    View.Plates = MoveTemp(Kept);
    View.Paths.Reset();
    View.Ghosts.Reset();
  }
  // VS-6 FX-08: V-17 fades in over 100 ms when the first ring appears (the maneuver start) and the rings of the
  // previous view fade out over 100 ms in the frame of the fighter pick; V-11 / V-12 fade in over 150 ms
  {
    TSet<int32> NowCand, NowPend;
    for (const FS08PlateView& P : View.Plates) {
      const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(P.X, P.Y));
      if (!Index) continue;
      if (P.Ring == ES08RingState::Candidate) NowCand.Add(*Index);
      if (P.Ring == ES08RingState::PendingMove || P.Ring == ES08RingState::PendingPlace) NowPend.Add(*Index);
    }
    const double Now = NowS();
    bool bKick = false;
    if (NowCand.Num() > 0 && PrevCandidates.Num() == 0) {
      CandFadeStartS = Now;
      bKick = true;
    }
    if (NowPend.Num() > 0 && PrevPending.Num() == 0) {
      PendFadeStartS = Now;
      bKick = true;
    }
    if (!S08FieldFx::ChoiceLegacy()) {
      for (const int32 I : PrevCandidates) {
        if (NowCand.Contains(I) || !SpaceCells.IsValidIndex(I)) continue;
        const FIntPoint Cell = SpaceCells[I];
        const FS08PlateView* Now0 = View.Find(Cell.X, Cell.Y);
        if (Now0 && Now0->Ring != ES08RingState::None) continue;
        if (Leaving.ContainsByPredicate([&Cell](const FS08PlateView& L) { return L.X == Cell.X && L.Y == Cell.Y; })) {
          continue;
        }
        FS08PlateView L;
        L.X = Cell.X;
        L.Y = Cell.Y;
        L.Ring = ES08RingState::Candidate;
        L.Flags = S08PlateFlags::Leaving;
        const float* Scale = PrevCandidateScale.Find(I);
        L.FigureScale = Scale ? *Scale : 1.0f;
        Leaving.Add(L);
        CandLeaveStartS = Now;
        bKick = true;
      }
    }
    PrevCandidates = NowCand;
    PrevPending = NowPend;
    PrevCandidateScale.Reset();
    for (const FS08PlateView& P : View.Plates) {
      if (P.Ring != ES08RingState::Candidate) continue;
      if (const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(P.X, P.Y))) {
        PrevCandidateScale.Add(*Index, P.FigureScale);
      }
    }
    for (const FS08PlateView& L : Leaving) {
      FS08PlateView* Existing = nullptr;
      for (FS08PlateView& P : View.Plates) {
        if (P.X == L.X && P.Y == L.Y) Existing = &P;
      }
      if (!Existing) {
        View.Plates.Add(L);
      } else if (Existing->Ring == ES08RingState::None) {
        Existing->Ring = ES08RingState::Candidate;
        Existing->Flags |= S08PlateFlags::Leaving;
        Existing->FigureScale = L.FigureScale;
      }
    }
    LastInputView = InView;
    if (bKick) KickFx();
  }
  uint32 Hash = S08MoveHighlight::ViewHash(View);
  Hash = HashCombineFast(Hash, static_cast<uint32>(Leaving.Num()) | (bChoiceOnly ? 0x10000u : 0u));
  if (Hash == AppliedHash && AppliedHash != 0) return 0;
  using S08MovePlateSpec::EChannel;
  const int32 NumChannels = static_cast<int32>(EChannel::Count);
  // per space the wanted data of every channel (an absent space = all None)
  TArray<const FS08PlateView*> BySpace;
  BySpace.Init(nullptr, SpaceCells.Num());
  for (const FS08PlateView& P : View.Plates) {
    if (const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(P.X, P.Y))) BySpace[*Index] = &P;
  }
  int32 Updates = 0;
  int32 Shown[4] = {0, 0, 0, 0};
  for (int32 I = 0; I < SpaceCells.Num(); ++I) {
    const FS08PlateView* P = BySpace[I];
    for (int32 C = 0; C < NumChannels; ++C) {
      const EChannel Channel = static_cast<EChannel>(C);
      float Data[S08MovePlateSpec::NumCustomData] = {0, 0, 0, 0, 0, 0, 0};
      float Z = 0.0f;
      bool bShow = false;
      if (P) {
        uint8 State = 0;
        ES08PlateColor Color = ES08PlateColor::Plate;
        switch (Channel) {
          case EChannel::Fill:
          case EChannel::Ring:
            State = static_cast<uint8>(P->Ring);
            if (P->Ring == ES08RingState::Conflict) Color = ES08PlateColor::Error;
            // VS-6 FX-08 (ВР-27): «choose this» on the field is board.choice (-S08ChoiceLegacy: the plate colour)
            if (!S08FieldFx::ChoiceLegacy() &&
                (P->Ring == ES08RingState::Candidate || P->Ring == ES08RingState::PendingMove ||
                 P->Ring == ES08RingState::PendingPlace)) {
              Color = ES08PlateColor::Choice;
            }
            // the ally mark exists on hover only (V-06); the fill draws nothing for the boost tier / ally / candidate
            bShow = P->Ring != ES08RingState::None &&
                       !(P->Ring == ES08RingState::AllyPass && !(P->Flags & S08PlateFlags::Hover));
            if (Channel == EChannel::Fill) {
              bShow &= P->Ring != ES08RingState::ReachBoost && P->Ring != ES08RingState::AllyPass &&
                          P->Ring != ES08RingState::Candidate && P->Ring != ES08RingState::PendingPlace &&
                          P->Ring != ES08RingState::Conflict;
            }
            Z = Channel == EChannel::Fill ? Style.ZFill
                : P->Ring == ES08RingState::Candidate ? Style.CandidateZ : Style.ZRing;
            break;
          case EChannel::Outline:
            State = static_cast<uint8>(P->Outline);
            Color = P->OutlineColor;
            bShow = P->Outline != ES08OutlineState::None;
            Z = Style.ZRing;
            break;
          case EChannel::Glyph:
            State = static_cast<uint8>(P->Glyph);
            Color = ES08PlateColor::Error;
            // the world glyph draws X (V-08) and "!" (V-09); order / step / hint are screen badges (MS-T-10)
            bShow = P->Glyph == ES08GlyphState::Invalid || P->Glyph == ES08GlyphState::Conflict;
            Z = S08MovePlateSpec::GlyphZ;
            break;
          default:
            break;
        }
        Data[S08MovePlateCpd::State] = State;
        Data[S08MovePlateCpd::Steps] = P->Ring == ES08RingState::Candidate && Channel == EChannel::Ring
                                           ? P->FigureScale
                                           : P->Steps / 10.0f;
        Data[S08MovePlateCpd::Chip] = P->Chip;
        Data[S08MovePlateCpd::GlyphIndex] = 0.0f;
        Data[S08MovePlateCpd::Flags] = P->Flags;
        Data[S08MovePlateCpd::Color] = static_cast<float>(Color);
        if (!bShow) {
          for (float& V : Data) V = 0.0f;
        }
      }
      // the channel slot never changes (BuildForBoard wrote it)
      Data[S08MovePlateCpd::Channel] = static_cast<float>(C);
      if (bShow) ++Shown[C];
      bool bSame = (bShow ? Z : -1e6f) == WrittenZ[C][I];
      for (int32 Slot = 0; bSame && Slot < S08MovePlateSpec::NumCustomData; ++Slot) {
        bSame = Written[C][I][Slot] == Data[Slot];
      }
      if (bSame) continue;
      WriteInstance(Channel, I, Data, bShow, Z);
      ++Updates;
    }
  }
  // VS-6 FX-14: the dashed last path and its arrowheads (the extra instances)
  WriteLastPaths(View.LastPaths);
  ++Updates;
  if (Updates > 0) Plates->MarkRenderStateDirty();
  AppliedHash = Hash;
  if (Updates > 0) {
    FS08Trace::Write(FString::Printf(TEXT("MS-HL view source=%s rev=%u plates=%d fill=%d ring=%d outline=%d glyph=%d paths=%d updates=%d hover=%s"),
                                     *View.Source, View.Revision, View.Plates.Num(), Shown[0], Shown[1], Shown[2],
                                     Shown[3], View.Paths.Num(), Updates,
                                     View.Hover.X >= 0 ? *Board.CellLabel(View.Hover.X, View.Hover.Y) : TEXT("-")));
  }
  return Updates;
}

int32 US08MoveHighlightComponent::InstanceOf(int32 X, int32 Y) const {
  const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(X, Y));
  return Index ? *Index : INDEX_NONE;
}

float US08MoveHighlightComponent::GetCustomData(S08MovePlateSpec::EChannel Channel, int32 Space, int32 Slot) const {
  const int32 C = static_cast<int32>(Channel);
  if (!Written.IsValidIndex(C) || !Written[C].IsValidIndex(Space) || !Written[C][Space].IsValidIndex(Slot)) return 0.0f;
  return Written[C][Space][Slot];
}

bool US08MoveHighlightComponent::IsInstanceVisible(S08MovePlateSpec::EChannel Channel, int32 Space) const {
  const int32 C = static_cast<int32>(Channel);
  if (!Plates || Space < 0 || Space >= SpaceCells.Num()) return false;
  const int32 Instance = IsmInstance(Channel, Space);
  if (!Plates->IsValidInstance(Instance)) return false;
  FTransform T;
  Plates->GetInstanceTransform(Instance, T, false);
  return !T.GetScale3D().IsNearlyZero() && WrittenZ.IsValidIndex(C) && WrittenZ[C].IsValidIndex(Space) &&
         WrittenZ[C][Space] > -1e5f;
}

// ---------------------------------------------------------------------------------------------------- VS-6 field FX

double US08MoveHighlightComponent::NowS() const {
  const UWorld* World = GetWorld();
  return World ? World->GetTimeSeconds() : 0.0;
}

void US08MoveHighlightComponent::WriteExtra(int32 Slot, float Channel, const FTransform& T, bool bShow,
                                            const float (&Data)[S08MovePlateSpec::NumCustomData]) {
  const int32 Instance = ExtraInstance(Slot);
  if (!Plates || !Plates->IsValidInstance(Instance)) return;
  for (int32 I = 0; I < S08MovePlateSpec::NumCustomData; ++I) {
    Plates->SetCustomDataValue(Instance, I, I == S08MovePlateCpd::Channel ? Channel : (bShow ? Data[I] : 0.0f), false);
  }
  FTransform Out = T;
  if (!bShow) Out.SetScale3D(FVector::ZeroVector);
  Plates->UpdateInstanceTransform(Instance, Out, false, false, true);
}

void US08MoveHighlightComponent::WriteLastPaths(const TArray<FS08LastPathView>& Paths) {
  using namespace S08MovePlateSpec;
  // FX-14 (ВР-29): one quad per edge (12 dashes, the team colour, the board.keyline edge), an arrowhead before the
  // destination along the last edge; PLACE is one straight edge from -> to. The alpha is LastMoveFade (the tracker).
  const float Width = Style.LastMoveWidthUU;
  const float HalfQuad = 0.5f * Width + Style.KeylineUU + 1.0f;
  const float Z = Style.PathZ;
  int32 Quad = 0, Arrow = 0;
  for (const FS08LastPathView& Path : Paths) {
    if (Path.Cells.Num() < 2) continue;
    TArray<TPair<FIntPoint, FIntPoint>> Edges;
    if (Path.bPlace) {
      Edges.Add({Path.Cells[0], Path.Cells.Last()});
    } else {
      for (int32 I = 0; I + 1 < Path.Cells.Num(); ++I) Edges.Add({Path.Cells[I], Path.Cells[I + 1]});
    }
    FVector LastDir = FVector::ZeroVector;
    FVector LastEnd = FVector::ZeroVector;
    for (const TPair<FIntPoint, FIntPoint>& E : Edges) {
      const FVector A = Board.CellToWorld(E.Key.X, E.Key.Y);
      const FVector B = Board.CellToWorld(E.Value.X, E.Value.Y);
      const FVector D = FVector(B.X - A.X, B.Y - A.Y, 0.0f);
      const float L = D.Size();
      if (L < 1.0f) continue;
      LastDir = D / L;
      LastEnd = B;
      if (Quad >= PathSlots) continue;
      float Data[NumCustomData] = {0, 0, 0, 0, 0, 0, 0};
      Data[S08MovePlateCpd::State] = static_cast<float>(Style.LastMoveDashPerEdge);
      Data[S08MovePlateCpd::Steps] = L;
      Data[S08MovePlateCpd::Chip] = HalfQuad;
      Data[S08MovePlateCpd::GlyphIndex] = Width;
      Data[S08MovePlateCpd::Color] = static_cast<float>(Path.Color);
      const FVector Mid = (A + B) * 0.5f + FVector(0.0f, 0.0f, Z);
      const FRotator Yaw(0.0f, FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X)), 0.0f);
      WriteExtra(Quad, PathChannel, FTransform(Yaw, Mid, FVector(L / 100.0f, 2.0f * HalfQuad / 100.0f, 1.0f)), true,
                 Data);
      ++Quad;
    }
    if (!LastDir.IsNearlyZero() && Arrow < ArrowSlots) {
      float Data[NumCustomData] = {0, 0, 0, 0, 0, 0, 0};
      Data[S08MovePlateCpd::Steps] = ArrowBoxUU;
      Data[S08MovePlateCpd::Color] = static_cast<float>(Path.Color);
      const FVector Centre = LastEnd - LastDir * (ArrowBackUU + 0.5f * ArrowBoxUU) + FVector(0.0f, 0.0f, Z + 0.05f);
      const FRotator Yaw(0.0f, FMath::RadiansToDegrees(FMath::Atan2(LastDir.Y, LastDir.X)), 0.0f);
      WriteExtra(PathSlots + Arrow, ArrowChannel, FTransform(Yaw, Centre, FVector(ArrowBoxUU / 100.0f)), true, Data);
      ++Arrow;
    }
  }
  const float Zero[NumCustomData] = {0, 0, 0, 0, 0, 0, 0};
  for (int32 I = Quad; I < PathSlots; ++I) WriteExtra(I, PathChannel, FTransform::Identity, false, Zero);
  for (int32 I = Arrow; I < ArrowSlots; ++I) WriteExtra(PathSlots + I, ArrowChannel, FTransform::Identity, false, Zero);
  if (Quad != LastPathQuads || Arrow != LastPathArrows) {
    FS08Trace::Write(FString::Printf(TEXT("MS-HL last-path paths=%d quads=%d arrows=%d dash=%d width=%.1f"),
                                     Paths.Num(), Quad, Arrow, Style.LastMoveDashPerEdge, Width));
  }
  LastPathQuads = Quad;
  LastPathArrows = Arrow;
}

void US08MoveHighlightComponent::WritePulse(double Ms) {
  using namespace S08MovePlateSpec;
  const int32 Slot = PathSlots + ArrowSlots;
  const float Zero[NumCustomData] = {0, 0, 0, 0, 0, 0, 0};
  const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(PulseCell.X, PulseCell.Y));
  if (!bPulseOn || !Index) {
    WriteExtra(Slot, PulseChannel, FTransform::Identity, false, Zero);
    if (Plates) Plates->MarkRenderStateDirty();
    return;
  }
  const S08FieldFx::FPulsePose Pose = S08FieldFx::ConfirmPulse(Ms, S08IconMotion::IsReducedMotion());
  float Data[NumCustomData] = {0, 0, 0, 0, 0, 0, 0};
  Data[S08MovePlateCpd::State] = 1.0f;
  Data[S08MovePlateCpd::Steps] = Pose.Fill;
  Data[S08MovePlateCpd::Chip] = Pose.Dim;
  Data[S08MovePlateCpd::Flags] = bPulseTarget ? S08PlateFlags::Occupied : 0;
  Data[S08MovePlateCpd::Color] = static_cast<float>(bPulseTarget ? ES08PlateColor::Target : ES08PlateColor::Plate);
  const float S = HalfUU * 2.0f / 100.0f * Pose.Scale;
  const FVector At = Board.CellToWorld(PulseCell.X, PulseCell.Y) + FVector(0.0f, 0.0f, Style.ZRing + 0.1f);
  WriteExtra(Slot, PulseChannel, FTransform(FRotator::ZeroRotator, At, FVector(S, S, 1.0f)), true, Data);
  if (Plates) Plates->MarkRenderStateDirty();
}

void US08MoveHighlightComponent::PlayConfirmPulse(int32 X, int32 Y, bool bTarget) {
  if (S08FieldFx::PulseLegacy() || !InstanceByCell.Contains(FS08BoardModel::CellKey(X, Y))) return;
  bPulseOn = true;
  PulseCell = FIntPoint(X, Y);
  bPulseTarget = bTarget;
  PulseStartS = NowS();
  FS08Trace::Write(FString::Printf(TEXT("MS-HL pulse cell=%s kind=%s ms=%d reduced=%d"), *Board.CellLabel(X, Y),
                                   bTarget ? TEXT("target") : TEXT("move"),
                                   FMath::RoundToInt(S08FieldFx::ConfirmPulseMs),
                                   S08IconMotion::IsReducedMotion() ? 1 : 0));
  KickFx();
}

void US08MoveHighlightComponent::SetPulseStatic(int32 X, int32 Y, bool bTarget, double Ms) {
  if (S08FieldFx::PulseLegacy() || !InstanceByCell.Contains(FS08BoardModel::CellKey(X, Y))) return;
  bPulseOn = true;
  PulseCell = FIntPoint(X, Y);
  bPulseTarget = bTarget;
  PulseStartS = -1.0e9;  // the bench: no timer, the pose at Ms
  WritePulse(Ms);
}

void US08MoveHighlightComponent::KickFx() {
  TickFx();
  UWorld* World = GetWorld();
  if (!World) return;
  FTimerManager& Timers = World->GetTimerManager();
  if (!Timers.IsTimerActive(FxTimer)) {
    Timers.SetTimer(FxTimer, FTimerDelegate::CreateWeakLambda(this, [this] { TickFx(); }), 1.0f / 60.0f, true);
  }
}

void US08MoveHighlightComponent::TickFx() {
  using namespace S08MovePlateSpec;
  const bool bReduced = S08IconMotion::IsReducedMotion();
  const double Now = NowS();
  bool bActive = false;
  if (PlateMid) {
    if (CandFadeStartS >= 0.0) {
      const float F = S08FieldFx::FadeIn((Now - CandFadeStartS) * 1000.0, S08FieldFx::CandidateInMs, bReduced);
      PlateMid->SetScalarParameterValue(ParamCandFade, F);
      if (F >= 1.0f) {
        CandFadeStartS = -1.0;
      } else {
        bActive = true;
      }
    }
    if (PendFadeStartS >= 0.0) {
      const float F = S08FieldFx::FadeIn((Now - PendFadeStartS) * 1000.0, S08FieldFx::PendingInMs, bReduced);
      PlateMid->SetScalarParameterValue(ParamPendFade, F);
      if (F >= 1.0f) {
        PendFadeStartS = -1.0;
      } else {
        bActive = true;
      }
    }
    if (CandLeaveStartS >= 0.0) {
      const float F = S08FieldFx::FadeIn((Now - CandLeaveStartS) * 1000.0, S08FieldFx::CandidateOutMs, bReduced);
      PlateMid->SetScalarParameterValue(ParamCandLeave, 1.0f - F);
      if (F >= 1.0f) {
        CandLeaveStartS = -1.0;
        Leaving.Reset();
        PlateMid->SetScalarParameterValue(ParamCandLeave, 1.0f);
        AppliedHash = 0;
        const FS08MoveDraftView Again = LastInputView;
        ApplyView(Again);  // the leaving rings go: the view of the pick frame without them
      } else {
        bActive = true;
      }
    }
  }
  if (bPulseOn && PulseStartS > -1.0e8) {
    const double Ms = (Now - PulseStartS) * 1000.0;
    if (S08FieldFx::ConfirmPulse(Ms, bReduced).bDone) {
      bPulseOn = false;  // the space keeps its own state (V-10 sent / V-04 destination) from the draft
    } else {
      bActive = true;
    }
    WritePulse(Ms);
  }
  if (!bActive) {
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(FxTimer);
  }
}

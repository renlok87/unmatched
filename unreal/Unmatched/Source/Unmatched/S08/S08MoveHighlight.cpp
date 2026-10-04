#include "S08MoveHighlight.h"
#include "S08Render.h"
#include "S08Team.h"
#include "S08TraceLog.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

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
  // V-17: candidate rings under the own fighters that may move (DE-017 decides which, and when)
  for (const FString& Id : Input.CandidateFighterIds) {
    for (const FS08BoardFighter& F : Fighters) {
      if (F.Id != Id || !F.IsAlive()) continue;
      if (FS08PlateView* P = At(FIntPoint(F.X, F.Y))) {
        Raise(P->Ring, ES08RingState::Candidate);
        P->FigureScale = F.bIsHero ? 1.0f : S08TeamRingSpec::SidekickScale;
      }
    }
  }
  if (FS08PlateView* P = At(Input.Hover)) P->Flags |= S08PlateFlags::Hover;
  FS08MoveDraftView View = Finish(Board, Fighters, Input.bLeaderPips, Spaces, Input.Source);
  View.Hover = Input.Hover;
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

void US08MoveHighlightComponent::EnsureChannels() {
  if (Channels.Num() == static_cast<int32>(S08MovePlateSpec::EChannel::Count)) return;
  Channels.Reset();
  for (int32 C = 0; C < static_cast<int32>(S08MovePlateSpec::EChannel::Count); ++C) {
    const S08MovePlateSpec::EChannel Channel = static_cast<S08MovePlateSpec::EChannel>(C);
    UInstancedStaticMeshComponent* Ism =
        NewObject<UInstancedStaticMeshComponent>(GetOwner() ? static_cast<UObject*>(GetOwner()) : this,
                                                 FName(FString(TEXT("MoveHL_")) + S08MovePlateSpec::ChannelName(Channel)));
    Ism->SetupAttachment(this);
    Ism->SetStaticMesh(PlaneMesh);
    Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Ism->SetNumCustomDataFloats(S08MovePlateSpec::NumCustomData);
    // translucent layers over each other in a fixed order: fill < ring < outline < glyph (03 §4.1)
    Ism->SetTranslucentSortPriority(10 + C);
    Ism->SetCastShadow(false);
    S08ApplyGameLayerPrimitive(Ism);
    if (IsRegistered()) Ism->RegisterComponent();
    Channels.Add(Ism);
  }
}

void US08MoveHighlightComponent::Initialize(UStaticMesh* Plane) {
  if (bInitialized) return;
  bInitialized = true;
  PlaneMesh = Plane;
  PlateMaterial = LoadObject<UMaterialInterface>(nullptr, S08MovePlateSpec::MaterialPath, nullptr, LOAD_NoWarn);
  EnsureChannels();
  ChannelMids.Reset();
  if (PlateMaterial && PlaneMesh) {
    for (int32 C = 0; C < Channels.Num(); ++C) {
      UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(PlateMaterial, this);
      Mid->SetScalarParameterValue(S08MovePlateSpec::ParamChannel, static_cast<float>(C));
      Channels[C]->SetMaterial(0, Mid);
      ChannelMids.Add(Mid);
    }
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
  for (UMaterialInstanceDynamic* Mid : ChannelMids) {
    if (!Mid) continue;
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
    // sRGB bytes of the profile -> linear (the W4-B colour rule, FLinearColor::FromSRGBColor)
    Mid->SetVectorParameterValue(ParamPlateColor, FLinearColor::FromSRGBColor(Style.PlateColor));
    Mid->SetVectorParameterValue(ParamKeylineColor, FLinearColor::FromSRGBColor(Style.KeylineColor));
    Mid->SetVectorParameterValue(ParamErrorColor, FLinearColor::FromSRGBColor(Style.InvalidColor));
    Mid->SetVectorParameterValue(ParamTeamP1Color, FLinearColor::FromSRGBColor(TeamP1Screen));
    Mid->SetVectorParameterValue(ParamTeamP2Color, FLinearColor::FromSRGBColor(TeamP2Screen));
  }
}

void US08MoveHighlightComponent::BuildForBoard(const FS08BoardModel& InBoard, const FS08MoveSelectionSpec& InStyle) {
  EnsureChannels();
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
  const int32 NumChannels = Channels.Num();
  Written.SetNum(NumChannels);
  WrittenZ.SetNum(NumChannels);
  for (int32 C = 0; C < NumChannels; ++C) {
    UInstancedStaticMeshComponent* Ism = Channels[C];
    Ism->ClearInstances();
    TArray<FTransform> Hidden;
    Hidden.Reserve(SpaceCells.Num());
    for (const FIntPoint& Cell : SpaceCells) {
      Hidden.Add(FTransform(FRotator::ZeroRotator, Board.CellToWorld(Cell.X, Cell.Y), FVector::ZeroVector));
    }
    Ism->AddInstances(Hidden, false);
    Written[C].Init(TArray<float>(), SpaceCells.Num());
    for (TArray<float>& Data : Written[C]) Data.Init(0.0f, S08MovePlateSpec::NumCustomData);
    WrittenZ[C].Init(-1e6f, SpaceCells.Num());
    Ism->MarkRenderStateDirty();
  }
  AppliedHash = 0;
  ApplyStyle(InStyle);
  FS08Trace::Write(FString::Printf(TEXT("MS-HL build n=%d spaces=%d channels=%d shape=%s style=%s plate=%s path=%s ready=%d"),
                                   BuildCount, SpaceCells.Num(), NumChannels, bSquare ? TEXT("square") : TEXT("circle"),
                                   *Style.Source, *S08ColorHex(Style.PlateColor), *S08ColorHex(Style.PathColor),
                                   bReady ? 1 : 0));
  FS08Trace::Write(S08MoveHighlight::CheckGeometry(Style).TraceLine(Style.Source));
}

void US08MoveHighlightComponent::WriteInstance(S08MovePlateSpec::EChannel Channel, int32 Instance,
                                               const float (&Data)[S08MovePlateSpec::NumCustomData], bool bShow,
                                               float Z) {
  const int32 C = static_cast<int32>(Channel);
  UInstancedStaticMeshComponent* Ism = Channels[C];
  for (int32 Slot = 0; Slot < S08MovePlateSpec::NumCustomData; ++Slot) {
    Ism->SetCustomDataValue(Instance, Slot, Data[Slot], false);
    Written[C][Instance][Slot] = Data[Slot];
  }
  const FIntPoint Cell = SpaceCells[Instance];
  const float Scale = bShow ? S08MovePlateSpec::HalfUU * 2.0f / 100.0f : 0.0f;
  const FVector Location = Board.CellToWorld(Cell.X, Cell.Y) + FVector(0.0f, 0.0f, Z);
  Ism->UpdateInstanceTransform(Instance, FTransform(FRotator::ZeroRotator, Location, FVector(Scale, Scale, bShow ? 1.0f : 0.0f)),
                               false, false, true);
  WrittenZ[C][Instance] = bShow ? Z : -1e6f;
}

int32 US08MoveHighlightComponent::ApplyView(const FS08MoveDraftView& View) {
  if (Channels.Num() != static_cast<int32>(S08MovePlateSpec::EChannel::Count) || SpaceCells.Num() == 0) return 0;
  const uint32 Hash = S08MoveHighlight::ViewHash(View);
  if (Hash == AppliedHash && AppliedHash != 0) return 0;
  using S08MovePlateSpec::EChannel;
  // per instance the wanted data of every channel (an absent space = all None)
  TArray<const FS08PlateView*> ByInstance;
  ByInstance.Init(nullptr, SpaceCells.Num());
  for (const FS08PlateView& P : View.Plates) {
    if (const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(P.X, P.Y))) ByInstance[*Index] = &P;
  }
  int32 Updates = 0;
  int32 Shown[4] = {0, 0, 0, 0};
  for (int32 I = 0; I < SpaceCells.Num(); ++I) {
    const FS08PlateView* P = ByInstance[I];
    for (int32 C = 0; C < Channels.Num(); ++C) {
      const EChannel Channel = static_cast<EChannel>(C);
      float Data[S08MovePlateSpec::NumCustomData] = {0, 0, 0, 0, 0, 0};
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
  if (Updates > 0) {
    for (UInstancedStaticMeshComponent* Ism : Channels) Ism->MarkRenderStateDirty();
  }
  AppliedHash = Hash;
  if (Updates > 0) {
    FS08Trace::Write(FString::Printf(TEXT("MS-HL view source=%s rev=%u plates=%d fill=%d ring=%d outline=%d glyph=%d paths=%d updates=%d hover=%s"),
                                     *View.Source, View.Revision, View.Plates.Num(), Shown[0], Shown[1], Shown[2],
                                     Shown[3], View.Paths.Num(), Updates,
                                     View.Hover.X >= 0 ? *Board.CellLabel(View.Hover.X, View.Hover.Y) : TEXT("-")));
  }
  return Updates;
}

const UInstancedStaticMeshComponent* US08MoveHighlightComponent::GetChannel(S08MovePlateSpec::EChannel Channel) const {
  const int32 C = static_cast<int32>(Channel);
  return Channels.IsValidIndex(C) ? Channels[C].Get() : nullptr;
}

int32 US08MoveHighlightComponent::InstanceOf(int32 X, int32 Y) const {
  const int32* Index = InstanceByCell.Find(FS08BoardModel::CellKey(X, Y));
  return Index ? *Index : INDEX_NONE;
}

float US08MoveHighlightComponent::GetCustomData(S08MovePlateSpec::EChannel Channel, int32 Instance, int32 Slot) const {
  const int32 C = static_cast<int32>(Channel);
  if (!Written.IsValidIndex(C) || !Written[C].IsValidIndex(Instance) || !Written[C][Instance].IsValidIndex(Slot)) return 0.0f;
  return Written[C][Instance][Slot];
}

bool US08MoveHighlightComponent::IsInstanceVisible(S08MovePlateSpec::EChannel Channel, int32 Instance) const {
  const int32 C = static_cast<int32>(Channel);
  const UInstancedStaticMeshComponent* Ism = GetChannel(Channel);
  if (!Ism || !Ism->IsValidInstance(Instance)) return false;
  FTransform T;
  Ism->GetInstanceTransform(Instance, T, false);
  return !T.GetScale3D().IsNearlyZero() && WrittenZ.IsValidIndex(C) && WrittenZ[C].IsValidIndex(Instance) &&
         WrittenZ[C][Instance] > -1e5f;
}

// FX-03 / FX-06 / FX-17 / FX-19 (VS-6 Z-2): the FX adapter of AS08FlowGameMode - the prewarm + asset resolver +
// grade of the spawner, the hover rim of CUE-001, the defense rim pulse of CUE-009. The game mode itself only
// calls the three S08Fx* entry points (one line each); everything else lives here and in S08/Fx/*.
//
// ВР-FX16: the dispatcher's AssetResolver names the REAL channel state - vfx=<NS_FX_*> when the registry system
// loads (none with -S08FxLegacy, missing while FX-13..FX-32 have not created it), clip=<AM_<Hero>_<Role>> when
// the v2 fighter carries the clip (no more clip=missing on a playing clip), sfx=<the sound token> when the
// sound row's asset loads.
#include "../S08FlowGameMode.h"

#include "Misc/Parse.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "../S08BoardActor.h"
#include "../S08FighterActor.h"
#include "../S08CueDispatcher.h"
#include "S08CueFx.h"
#include "S08CueFxSpawner.h"
#include "../S08CueSound.h"
#include "../S08HeroesV2.h"
#include "../S08IconMotion.h"
#include "../S08MoveHighlight.h"
#include "../S08Team.h"
#include "../S08TraceLog.h"
#include "S08FieldFx.h"

namespace {

S08HeroesV2::EClip ClipOfRole(const FString& Role) {
  if (Role == TEXT("LungeAttack")) return S08HeroesV2::EClip::LungeAttack;
  if (Role == TEXT("HitReact")) return S08HeroesV2::EClip::HitReact;
  if (Role == TEXT("DeathSettle")) return S08HeroesV2::EClip::DeathSettle;
  return S08HeroesV2::EClip::None;
}

/** The grade of the profile's paste spec: the measured fit of the engine tone curve (the paste may be off - the
 *  fit still holds); every FX material runs the same inverse curve as M_ConceptPaste. Read when needed (the Z-2
 *  review: read once at the board-ready hook, before the board's rebuild, it was the neutral grade - the placard
 *  MIDs then showed a third of the token's emissive, the peach "cream"). */
void ApplyProfileGrade(const AS08BoardActor& Board, US08CueFxSpawnerComponent& Spawner) {
  const FS08ConceptPasteSpec& Paste = Board.GetConceptPasteSpec();
  if (Paste.Grade == ES08ConceptGrade::AcesInverse) {
    const FVector& K = Paste.FitScale;
    const FVector& P = Paste.FitPower;
    Spawner.SetGrade(FLinearColor(K.X, K.Y, K.Z, 0.0f), FLinearColor(1.0f / P.X, 1.0f / P.Y, 1.0f / P.Z, 0.0f),
                     TEXT("profile"));
  } else {
    Spawner.SetGrade(FLinearColor(1.0f, 1.0f, 1.0f, 0.0f), FLinearColor(1.0f, 1.0f, 1.0f, 0.0f), TEXT("neutral"));
  }
}

}  // namespace

void AS08FlowGameMode::S08FxBoardReady() {
  if (!BoardActor || !GetWorld()) return;
  if (!CueFxSpawner) CueFxSpawner = NewObject<US08CueFxSpawnerComponent>(this);
  if (!CueFxSpawner->IsRegistered()) CueFxSpawner->RegisterComponent();
  // the prewarm (load + pool prime + one invisible spawn) once per spawner (= per game mode): before the first
  // show, so the first frame of a system never pays the compile / pool price
  if (!CueFxSpawner->HasPrewarmed()) CueFxSpawner->Prewarm();
  ApplyProfileGrade(*BoardActor, *CueFxSpawner);  // re-read where an FX is shown (the board may rebuild after)
  // VS-6 FX-14 (ВР-29): the opponent's last path holds holdMs after its reveal and appears over inMs (profile
  // moveSelection.lastMove); -S08LastMoveLegacy keeps the MS-T-17 contour with the MS-P-03 exit rule only
  const FS08MoveSelectionSpec MoveSel = BoardActor->ActiveMoveSelection();
  LastMoveTracker.HoldMs = S08FieldFx::LastMoveLegacy() ? 0.0 : static_cast<double>(MoveSel.LastMoveHoldMs);
  LastMoveTracker.InMs = S08FieldFx::LastMoveLegacy() ? 0.0 : static_cast<double>(MoveSel.LastMoveInMs);
  FieldFx.Reset();
  // ВР-FX16: the honest channel tokens of every `CUE fx` line
  CueDispatcher.AssetResolver = [this](const FString& CueId, const FString& Channel, const FString& Subject) {
    if (Channel == TEXT("vfx")) {
      if (!S08CueFx::FxEnabled()) return FString(TEXT("none"));
      // FX-28: CUE-014 is per hero - the subject's look-dev key picks its system
      const AS08FighterActor* Actor = BoardActor ? BoardActor->FindFighterActor(Subject) : nullptr;
      const FString HeroKey = Actor && Actor->GetHeroV2Spec() ? FString(Actor->GetHeroV2Spec()->Key) : FString();
      const S08CueFx::FEntry* E = S08CueFx::Find(CueId, HeroKey);
      if (!E) return FString();
      if (E->System.IsEmpty()) return FString();  // missing until FX-28 names the hero's system
      return LoadObject<UNiagaraSystem>(nullptr, *E->System) ? S08CueFx::SystemName(E->System) : FString();
    }
    if (Channel == TEXT("clip")) {
      const FS08CueRow* Row = S08CueRows::Find(S08CueRows::Combat(), CueId);
      if (!Row || Row->ClipRole.IsEmpty() || !BoardActor) return FString(TEXT("none"));
      const AS08FighterActor* Actor = BoardActor->FindFighterActor(Subject);
      const FString Asset = Actor ? Actor->GetHeroClipAssetName(ClipOfRole(Row->ClipRole)) : FString();
      return Asset.IsEmpty() ? FString() : Asset;  // missing when this figure carries no such v2 clip
    }
    if (Channel == TEXT("sfx")) {
      const FS08SoundRow* Row = S08SoundRows::Find(CueId);
      if (!Row || Row->SoundPath.IsEmpty()) return FString(TEXT("none"));
      return LoadObject<USoundBase>(nullptr, *Row->SoundPath) ? S08SoundRows::ShortName(Row->SoundPath)
                                                              : FString();
    }
    return FString();
  };
  // FX-28: the socket of the hero's CUE-014 entry (Weapon / Root) in the show line
  CueDispatcher.SocketResolver = [this](const FString& CueId, const FString& Subject) {
    const AS08FighterActor* Actor = BoardActor ? BoardActor->FindFighterActor(Subject) : nullptr;
    const FString HeroKey = Actor && Actor->GetHeroV2Spec() ? FString(Actor->GetHeroV2Spec()->Key) : FString();
    const S08CueFx::FEntry* E = HeroKey.IsEmpty() ? nullptr : S08CueFx::Find(CueId, HeroKey);
    return E && E->HeroKey == HeroKey && E->bSocket ? E->Socket : FString();
  };
}

void AS08FlowGameMode::S08FxHoverChanged(const FString& NewId, const FString& OldId) {
  // FX-06: the rim follows the cursor's figure - in over 150 ms (ease-out to 0.6, width 0.2, held), out 120 ms
  // (S08FigureFx::HoverRim / HoverLeaveMs, milliseconds); a fallen figure shows no rim; -S08FxLegacy writes
  // nothing (the CUE row still traces).
  auto Rim = [&](const FString& Id, bool bOn) {
    if (Id.IsEmpty() || !BoardActor || !S08CueFx::FxEnabled()) return;
    AS08FighterActor* Actor = BoardActor->FindFighterActor(Id);
    if (!Actor || Actor->IsInDeathHold()) return;
    if (bOn) {
      Actor->PlayRimPulse(S08FigureFx::HoverRim);
    } else {
      Actor->StopRim(S08FigureFx::HoverLeaveMs);
    }
  };
  Rim(OldId, false);
  Rim(NewId, true);
  TArray<FString> Lines;
  CueDispatcher.Feed(TEXT("CUE-001"), NewId, -1, NowMs(), Lines);
  WriteCueLines(Lines);
}

void AS08FlowGameMode::S08FxDefensePlayed(const FString& DefenderId) {
  // FX-17 (ВР-23): the cream rim pulse of the defender from t0 = event + 150 ms (CUE-009 feedback_delay_ms) -
  // 0 -> 1 over 60 ms, held to t0+180, 0 at t0+300 (S08FigureFx::DefenseRim); the CUE row (mat=Rim, no vfx) has
  // already traced above the call.
  if (DefenderId.IsEmpty() || !BoardActor || !S08CueFx::FxEnabled()) return;
  if (AS08FighterActor* Actor = BoardActor->FindFighterActor(DefenderId)) {
    if (!Actor->IsInDeathHold()) Actor->PlayRimPulse(S08FigureFx::DefenseRim);
  }
  S08FxDefenseShot(DefenderId);  // VS-6 F2: the live frame of the pulse (the FX capture hook)
}

void AS08FlowGameMode::S08FxBenchStep(const FString& Spec) {
  // -BenchFx=<mode>[,<id>][,<value>]: placard | hover | rim | rimout | flash | hit | star | off
  //   placard      the FX-02 test placard: NS_FX_PlacardStar (the flipbook print) + the three SDF quads
  //                (disk / diamond / chevron) in a row over the board centre
  //   hover[,<id>] the FX-06 hold state: rim 0.6 x width 0.2 + the CUE-001 line (src=flag, like INPUT select)
  //   rim[,<id>]   the FX-17 / FX-19 peak state: rim 1.0 x width 0.35 (t0+60..C+270)
  //   rimout[,<id>] the way out (C+300): rim 0.5 x width 0.35
  //   flash[,<id>] the FX-19 flash frame (C+0..C+35): FxFlash a = 1, no rim
  //   hit[,<id>]   flash 1 + rim 1 (the composite frame for the grey / deuteranopia rows)
  // The channel values are written straight to CPD (deterministic, no timers in the bench); the curves run in
  // the unit tests and in the live demo.
  // VS-6 F1: several steps separated by ';' (the field modes of S08FxBenchField land together at the end)
  if (Spec.Contains(TEXT(";"))) {
    TArray<FString> Steps;
    Spec.ParseIntoArray(Steps, TEXT(";"), true);
    for (const FString& Step : Steps) S08FxBenchStep(Step);
    S08FxBenchFieldFinish();
    return;
  }
  TArray<FString> Parts;
  Spec.ParseIntoArray(Parts, TEXT(","), true);
  if (Parts.Num() == 0) return;
  const FString& Mode = Parts[0];
  const FString Id = Parts.IsValidIndex(1) ? Parts[1] : FString();
  UWorld* World = GetWorld();
  if (!World || !BoardActor) {
    FS08Trace::Write(FString::Printf(TEXT("FX bench mode=%s error=no board"), *Mode));
    return;
  }
  if (!CueFxSpawner) S08FxBoardReady();  // the bench builds no flow: the spawner (prewarm, grade) comes here
  // VS-6 F2: + star / heal; VS-6 F3: + ash / vortex / arc
  if (S08FxBenchField(Mode, Parts) || S08FxBenchCombat(Mode, Parts) || S08FxBenchAbility(Mode, Parts)) {
    S08FxBenchFieldFinish();
    return;
  }
  auto Rim = [&](const FString& FighterId, float Intensity, float Width) {
    if (AS08FighterActor* Actor = BoardActor->FindFighterActor(FighterId)) {
      Actor->SetFxBenchChannels(0.0f, Intensity, Width);
    }
  };
  auto Flash = [&](const FString& FighterId, float A) {
    if (AS08FighterActor* Actor = BoardActor->FindFighterActor(FighterId)) {
      Actor->SetFxBenchChannels(A, 0.0f, 0.35f);
    }
  };
  if (Mode == TEXT("placard")) {
    // the FX-02 placard: the Niagara star (frame 0 of the print flipbook) + three SDF quads, a row over the
    // board centre; 96 uu each (the Z-2 review: at 32 uu the edge / keyline bands were sub-pixel on K1)
    const FVector Centre = BoardActor->GetActorLocation();
    const float Spacing = 112.0f;
    if (CueFxSpawner) ApplyProfileGrade(*BoardActor, *CueFxSpawner);  // the board is built now: the real profile
    if (CueFxSpawner) {
      UNiagaraComponent* Star = CueFxSpawner->SpawnSystem(
          TEXT("/Game/S08/FX/Systems/NS_FX_PlacardStar"),
          FTransform(FRotator(0.0f, 90.0f, 0.0f), Centre + FVector(2.0f * Spacing, 0.0f, 60.0f)));
      const bool bStarOk = Star && Star->IsRegistered();
      FS08Trace::Write(FString::Printf(TEXT("FX bench placard star=%s"), bStarOk ? TEXT("registered") : TEXT("failed")));
    }
    static const TCHAR* const QuadMis[] = {TEXT("MI_FX_PlacardDisk"), TEXT("MI_FX_PlacardDiamond"),
                                          TEXT("MI_FX_PlacardChevron")};
    int32 Quads = 0;
    for (int32 I = 0; I < 3; ++I) {
      const FString MiPath = FString::Printf(TEXT("/Game/S08/FX/Materials/%s.%s"), QuadMis[I], QuadMis[I]);
      UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, *MiPath);
      if (!Mi) continue;
      UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
      if (!Plane) continue;
      UStaticMeshComponent* Quad = NewObject<UStaticMeshComponent>(BoardActor);
      Quad->SetStaticMesh(Plane);
      Quad->SetMaterial(0, Mi);
      Quad->SetWorldLocation(Centre + FVector((I - 1) * Spacing, 0.0f, 60.0f));
      // the engine plane faces -Z (its normal down): flip it up and face the board camera (yaw 90)
      Quad->SetWorldRotation(FRotator(90.0f, 90.0f, 0.0f));
      Quad->SetWorldScale3D(FVector(0.96f));  // 100 uu plane x 0.96 = 96 uu quad
      Quad->SetCollisionEnabled(ECollisionEnabled::NoCollision);
      Quad->SetTranslucentSortPriority(S08CueFx::TranslucentSortPriority);
      Quad->RegisterComponentWithWorld(World);
      // the runtime grade of the active profile (the placard quads are not Niagara - a plain MID override)
      if (CueFxSpawner) {
        if (UMaterialInstanceDynamic* Mid = Quad->CreateAndSetMaterialInstanceDynamic(0)) {
          Mid->SetVectorParameterValue(TEXT("GradeScale"), CueFxSpawner->GetGradeScale());
          Mid->SetVectorParameterValue(TEXT("GradePow"), CueFxSpawner->GetGradePow());
        }
      }
      ++Quads;
    }
    FS08Trace::Write(FString::Printf(TEXT("FX bench placard sdf=%d"), Quads));
    return;
  }
  if (Mode == TEXT("hover")) {
    Rim(Id, 0.6f, 0.2f);
    TArray<FString> Lines;
    CueDispatcher.Feed(TEXT("CUE-001"), Id, -1, NowMs(), Lines);
    WriteCueLines(Lines);
    FS08Trace::Write(FString::Printf(TEXT("INPUT hover src=flag fighter=%s"), *Id));
    return;
  }
  if (Mode == TEXT("rim")) { Rim(Id, 1.0f, 0.35f); return; }
  if (Mode == TEXT("rimout")) { Rim(Id, 0.5f, 0.35f); return; }
  if (Mode == TEXT("flash")) { Flash(Id, 1.0f); return; }
  if (Mode == TEXT("hit")) {
    if (AS08FighterActor* Actor = BoardActor->FindFighterActor(Id)) {
      Actor->SetFxBenchChannels(1.0f, 1.0f, 0.35f);
    }
    return;
  }
  FS08Trace::Write(FString::Printf(TEXT("FX bench mode=%s error=unknown"), *Mode));
}

// ================================================================================================= VS-6 F1 field FX

namespace {
FString CellSubject(const FIntPoint& Cell) { return FString::Printf(TEXT("cell-%d-%d"), Cell.X, Cell.Y); }
/** -BenchFx field steps accumulate here and land once (one plate view; the marks of every fighter). Bench only. */
struct FFieldBench {
  TMap<FString, TMap<int32, double>> Marks;
  FS08MoveDraftInput Draft;
  bool bDraftSet = false;
  struct FPulse {
    FIntPoint Cell;
    bool bTarget = false;
    double Ms = 0.0;
  };
  TArray<FPulse> Pulses;
  struct FSpawn {
    FString Cue;
    FTransform Xf;
    double Ms = 0.0;
  };
  TArray<FSpawn> Spawns;
  bool bSpawned = false;
};
FFieldBench GFieldBench;
}  // namespace

void AS08FlowGameMode::S08FxBoardInput(const FS09InputResult& Result, const FIntPoint& Cell, const FString& FighterId) {
  // the same decision as the UI sound of this release (S08SoundRows::BoardUiCue, PlayBoardUiSound) - so the CUE row
  // and UI-SELECT / UI-CONFIRM / UI-REJECT go out in one frame (FX-09 AU2 |dt| <= 17 ms)
  const bool bRefused = Result.Toast.IsSet() || Result.IllegalCell.X >= 0;
  const bool bCommand = Result.bBeginManeuver || Result.bConfirmManeuver;
  const FS08BoardFighter* Fighter =
      FighterId.IsEmpty() ? nullptr
                          : Fighters.FindByPredicate([&FighterId](const FS08BoardFighter& F) { return F.Id == FighterId; });
  const bool bPickedOwn = Result.bSelectionChanged && Fighter && !Fighter->OwnerId.IsEmpty() &&
                          Fighter->OwnerId == ViewerIdNow();
  const TCHAR* Cue = S08SoundRows::BoardUiCue(bRefused, bCommand, bPickedOwn, Result.bSelectionChanged);
  if (!Cue) return;
  const FString CueId(Cue);
  FString Subject;
  if (CueId == TEXT("CUE-002")) {
    Subject = FighterId;  // FX-07: the ring itself follows SetSelected (S08FieldFx FS08FieldMarks)
  } else if (CueId == TEXT("CUE-004")) {
    Subject = Result.IllegalCell.X >= 0 ? CellSubject(Result.IllegalCell) : FString(TEXT("cursor"));
  } else {
    Subject = Cell.X >= 0 ? CellSubject(Cell) : (FighterId.IsEmpty() ? FString(TEXT("target")) : FighterId);
  }
  TArray<FString> Lines;
  CueDispatcher.Feed(CueId, Subject, -1, NowMs(), Lines);
  WriteCueLines(Lines);
  // FX-09: a click on a space of the draft (a destination pick or the confirm) pulses that space; a fighter click
  // keeps its own answer (the ring / the inspector)
  if (CueId == TEXT("CUE-003") && Cell.X >= 0 && FighterId.IsEmpty() && BoardActor) {
    BoardActor->PlayConfirmPulse(Cell.X, Cell.Y, false);
  }
}

void AS08FlowGameMode::S08FxTargetConfirmed(const FString& TargetId) {
  const FS08BoardFighter* Target = FindFighter(TargetId);
  if (!Target || !BoardActor) return;
  TArray<FString> Lines;
  CueDispatcher.Feed(TEXT("CUE-003"), TargetId, -1, NowMs(), Lines);
  WriteCueLines(Lines);
  BoardActor->PlayConfirmPulse(Target->X, Target->Y, true);
}

void AS08FlowGameMode::S08FxMovePlans(const TArray<FS08MovePlan>& Plans) {
  const double Now = static_cast<double>(NowMs());
  for (const FS08MovePlan& Plan : Plans) {
    if (!BoardActor || !BoardActor->FindFighterActor(Plan.FighterId)) continue;
    // a merge of the same seq schedules the same plans again: one CUE-007 row and one dust per (fighter, seq)
    const FString Key = FString::Printf(TEXT("%s|%d"), *Plan.FighterId, Plan.Seq);
    if (FieldFx.DustDone.Contains(Key) ||
        FieldFx.Moves.ContainsByPredicate([&Plan](const FS08FieldFxState::FPendingMove& M) {
          return M.FighterId == Plan.FighterId && M.Seq == Plan.Seq;
        })) {
      continue;
    }
    // CUE-007 jump_to_final: a new move of the figure lands its old one - the old landing shows no dust
    FieldFx.Moves.RemoveAll([&Plan](const FS08FieldFxState::FPendingMove& M) { return M.FighterId == Plan.FighterId; });
    FS08FieldFxState::FPendingMove M;
    M.FighterId = Plan.FighterId;
    M.Seq = Plan.Seq;
    M.StartAtMs = Now + Plan.StartMs;
    M.LandAtMs = Now + Plan.ArriveMs();
    M.DurationMs = FMath::RoundToInt(Plan.DurationMs());
    M.Destination = Plan.Destination();
    M.bSnapped = Plan.bSnapped;
    FieldFx.Moves.Add(M);
  }
  S08FxTick();  // the moves that start now are traced in this frame
}

void AS08FlowGameMode::S08FxAttackDeclared(const FString& AttackerId, const FString& TargetId, int32 Seq) {
  if (AttackerId.IsEmpty() || TargetId.IsEmpty()) return;
  FS08FieldFxState::FPendingChevrons C;
  C.AttackerId = AttackerId;
  C.TargetId = TargetId;
  C.Seq = Seq;
  C.ShowAtMs = static_cast<double>(NowMs()) + S08FieldFx::ChevronDelayMs;  // t0 = event + feedback_delay_ms
  FieldFx.Chevrons.Add(C);
}

void AS08FlowGameMode::S08FxCueLines(const TArray<FString>& Lines) {
  // FX-16: CUE-009 / 010 / 011 / 013 interrupt CUE-008 (the dispatcher writes `cut=interrupt`): the chevrons go
  for (const FString& Line : Lines) {
    // VS-6 F2 FX-23: a cut staging (replace / reconnect / catch-up) drops the stars of its seq not yet shown
    if (Line.StartsWith(TEXT("CUE combat seq=")) && Line.Contains(TEXT(" stage=end ")) && !Line.Contains(TEXT(" cut=0"))) {
      int32 CutSeq = -1;
      FParse::Value(*Line, TEXT("seq="), CutSeq);
      CombatFx.Stars.RemoveAll([CutSeq](const FS08CombatFxState::FPendingStar& S) { return S.Seq == CutSeq; });
    }
    if (!Line.StartsWith(TEXT("CUE fx done id=CUE-008 ")) || !Line.Contains(TEXT(" cut=interrupt"))) continue;
    FieldFx.Chevrons.Reset();
    if (UNiagaraComponent* C = FieldFx.LiveChevrons.Get()) {
      if (C->IsActive()) {
        // ВР-VS6-09: the carrier has no per-instance fade parameter - the cut is the frame of the interrupt
        C->DeactivateImmediate();
        FS08Trace::Write(FString::Printf(TEXT("FX cut id=CUE-008 subject=%s seq=%d vfx=NS_FX_AttackChevrons cut=interrupt"),
                                         *FieldFx.LiveChevronsAttacker, FieldFx.LiveChevronsSeq));
      }
    }
    FieldFx.LiveChevrons = nullptr;
  }
}

namespace {
/** FX-16: the transform of the chevron quad from the attacker's to the target's centre (the plane spans the whole
 *  segment; M_FX_BoardPrint draws the chevrons at 30 / 50 / 70 % of it, sized from its world width). */
bool ChevronTransform(const FVector& From, const FVector& To, FTransform& Out) {
  const FVector D(To.X - From.X, To.Y - From.Y, 0.0f);
  const float L = D.Size();
  if (L < 10.0f) return false;
  const float W = S08FieldFx::ChevronWidthUU(L, 41.0f);
  const FVector Mid = (From + To) * 0.5f;
  Out = FTransform(FRotator(0.0f, FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X)), 0.0f),
                   FVector(Mid.X, Mid.Y, FMath::Min(From.Z, To.Z) + S08FieldFx::ChevronZ),
                   FVector(L / 100.0f, (W + 4.0f) / 100.0f, 1.0f));
  return true;
}
}  // namespace

void AS08FlowGameMode::S08FxTick() {
  S08FxCombatTick();  // VS-6 F2: the stars at C+70, the heals, the FX capture hook
  S08FxAbilityTick();  // VS-6 F3: the gaze staging, the embers of the dissolving figures
  if (FieldFx.Moves.Num() == 0 && FieldFx.Chevrons.Num() == 0) return;
  const double Now = static_cast<double>(NowMs());
  const bool bReduced = S08IconMotion::IsReducedMotion();
  // FX-13: CUE-007 from the start of each move, the dust in the landing frame (reduced motion / speed "none" /
  // a snapped move: a jump, no dust; -S08FxLegacy: none)
  for (int32 I = 0; I < FieldFx.Moves.Num();) {
    FS08FieldFxState::FPendingMove& M = FieldFx.Moves[I];
    if (!M.bFed && Now >= M.StartAtMs) {
      M.bFed = true;
      TArray<FString> Lines;
      CueDispatcher.Feed(TEXT("CUE-007"), M.FighterId, M.Seq, NowMs(), Lines, 0, M.bSnapped ? 0 : M.DurationMs,
                         /*bStaged=*/true);
      WriteCueLines(Lines);
    }
    if (M.bFed && Now >= M.LandAtMs) {
      const FString Key = FString::Printf(TEXT("%s|%d"), *M.FighterId, M.Seq);
      FieldFx.DustDone.Add(Key);
      if (!M.bSnapped && !bReduced && S08CueFx::FxEnabled() && CueFxSpawner) {
        ApplyProfileGrade(*BoardActor, *CueFxSpawner);
        const FVector At(M.Destination.X, M.Destination.Y, M.Destination.Z + S08FieldFx::DustZ);
        UNiagaraComponent* Dust = CueFxSpawner->Spawn(TEXT("CUE-007"), S08FieldFx::DustTransform(At));
        FS08Trace::Write(FString::Printf(TEXT("FX dust fighter=%s seq=%d at=(%.0f,%.0f) result=%s"), *M.FighterId,
                                         M.Seq, At.X, At.Y, Dust ? TEXT("spawned") : TEXT("missing")));
      }
      FieldFx.Moves.RemoveAt(I);
      continue;
    }
    ++I;
  }
  // FX-16: the chevrons at t0 = event + 150 (skipped when the cue was cut before its show)
  for (int32 I = 0; I < FieldFx.Chevrons.Num();) {
    const FS08FieldFxState::FPendingChevrons C = FieldFx.Chevrons[I];
    if (Now < C.ShowAtMs) {
      ++I;
      continue;
    }
    FieldFx.Chevrons.RemoveAt(I);
    if (!S08CueFx::FxEnabled() || !CueFxSpawner || !BoardActor) continue;
    const AS08FighterActor* A = BoardActor->FindFighterActor(C.AttackerId);
    const AS08FighterActor* T = BoardActor->FindFighterActor(C.TargetId);
    FTransform Xf;
    if (!A || !T || !ChevronTransform(A->GetActorLocation(), T->GetActorLocation(), Xf)) continue;
    ApplyProfileGrade(*BoardActor, *CueFxSpawner);
    UNiagaraComponent* Comp = CueFxSpawner->Spawn(TEXT("CUE-008"), Xf);
    if (Comp) {
      // the speed of the combat (DE-025) scales the 600 ms; reduced motion / speed "none": the end state in 100 ms
      const float Mul = CombatSpeedMul();
      const float Dilation = bReduced || Mul <= 0.0f ? 6.0f : 1.0f / Mul;
      Comp->SetCustomTimeDilation(Dilation);
      FieldFx.LiveChevrons = Comp;
      FieldFx.LiveChevronsAttacker = C.AttackerId;
      FieldFx.LiveChevronsSeq = C.Seq;
    }
    FS08Trace::Write(FString::Printf(TEXT("FX chevrons attacker=%s target=%s seq=%d len=%.0f result=%s"), *C.AttackerId,
                                     *C.TargetId, C.Seq, Xf.GetScale3D().X * 100.0f, Comp ? TEXT("spawned") : TEXT("missing")));
  }
}

bool AS08FlowGameMode::S08FxBenchField(const FString& Mode, const TArray<FString>& Parts) {
  // -BenchFx (VS-6 F1) field modes, ';' between steps:
  //   select,<id>[,<ms>]       FX-07 the V-05 ring at <ms> of its appear (default 250)
  //   target,<id>[,<ms>]       FX-15 the arcs + the IC-35 world token at <ms> (default 150)
  //   choice[,<id>...]         FX-08 V-17 rings under the viewer's fighters (or the listed ones)
  //   pendingmove,<x>,<y>,...  FX-08 V-11 on the listed spaces; pendingplace,... V-12
  //   pulse,<x>,<y>,<ms>[,target]  FX-09 the confirm pulse at <ms>
  //   lastpath,<id>,<x0>,<y0>,<x1>,<y1>...[,place]  FX-14 the dashed path of <id>'s move (its team colour)
  //   dust,<x>,<y>,<ms>        FX-13 NS_FX_Dust frozen at <ms>
  //   chevrons,<a>,<t>,<ms>    FX-16 NS_FX_AttackChevrons frozen at <ms> after t0
  auto Num = [&Parts](int32 I, double Default) {
    return Parts.IsValidIndex(I) && Parts[I].IsNumeric() ? FCString::Atod(*Parts[I]) : Default;
  };
  if (Mode == TEXT("select") || Mode == TEXT("target")) {
    AS08FighterActor* Actor = Parts.IsValidIndex(1) ? BoardActor->FindFighterActor(Parts[1]) : nullptr;
    if (!Actor) return false;
    const bool bRing = Mode == TEXT("select");
    const double Ms = Num(2, bRing ? S08FieldFx::SelectionAppearMs : S08FieldFx::TargetAppearMs);
    GFieldBench.Marks.FindOrAdd(Parts[1]).Add(bRing ? 0 : 1, Ms);
    FS08Trace::Write(FString::Printf(TEXT("FX bench %s fighter=%s ms=%.0f"), *Mode, *Parts[1], Ms));
    return true;
  }
  if (Mode == TEXT("choice")) {
    if (Parts.Num() > 1) {
      for (int32 I = 1; I < Parts.Num(); ++I) GFieldBench.Draft.CandidateFighterIds.Add(Parts[I]);
    } else {
      for (const FS08BoardFighter& F : Fighters) {
        if (F.OwnerId == BenchViewerId && F.IsAlive()) GFieldBench.Draft.CandidateFighterIds.Add(F.Id);
      }
    }
    GFieldBench.bDraftSet = true;
    return true;
  }
  if (Mode == TEXT("pendingmove") || Mode == TEXT("pendingplace")) {
    GFieldBench.Draft.bPending = true;
    GFieldBench.Draft.bPendingPlace = Mode == TEXT("pendingplace");
    for (int32 I = 1; I + 1 < Parts.Num(); I += 2) {
      GFieldBench.Draft.PendingCells.Add(FS08BoardModel::CellKey(FCString::Atoi(*Parts[I]), FCString::Atoi(*Parts[I + 1])));
    }
    GFieldBench.bDraftSet = true;
    return true;
  }
  if (Mode == TEXT("pulse")) {
    if (Parts.Num() < 3) return false;
    GFieldBench.Pulses.Add({FIntPoint(FCString::Atoi(*Parts[1]), FCString::Atoi(*Parts[2])),
                            Parts.Num() > 4 && Parts[4] == TEXT("target"), Num(3, 0.0)});
    FS08Trace::Write(FString::Printf(TEXT("FX bench pulse cell=%s,%s ms=%.0f"), *Parts[1], *Parts[2], Num(3, 0.0)));
    return true;
  }
  if (Mode == TEXT("lastpath")) {
    if (Parts.Num() < 6) return false;
    const FS08BoardFighter* F = FindFighter(Parts[1]);
    TArray<FIntPoint> Cells;
    bool bPlace = false;
    for (int32 I = 2; I < Parts.Num(); ++I) {
      if (Parts[I] == TEXT("place")) {
        bPlace = true;
      } else if (I + 1 < Parts.Num() && Parts[I + 1] != TEXT("place")) {
        Cells.Add(FIntPoint(FCString::Atoi(*Parts[I]), FCString::Atoi(*Parts[I + 1])));
        ++I;
      }
    }
    if (F && BoardActor) {
      const ES08TeamSlot Look =
          S08TeamLook(BoardActor->TeamOfFighter(*F), F->OwnerId == BenchViewerId, BoardActor->GetTeamColorMode());
      GFieldBench.Draft.LastMove.Color = Look == ES08TeamSlot::P1 ? ES08PlateColor::TeamP1 : ES08PlateColor::TeamP2;
    }
    if (Cells.Num() >= 2) {
      GFieldBench.Draft.LastMove.From.Add(Cells[0]);
      GFieldBench.Draft.LastMove.To.Add(Cells.Last());
      GFieldBench.Draft.LastMove.Paths.Add(Cells);
      GFieldBench.Draft.LastMove.Places.Add(bPlace);
    }
    GFieldBench.bDraftSet = true;
    return true;
  }
  if (Mode == TEXT("dust") || Mode == TEXT("chevrons")) {
    if (!CueFxSpawner) return false;
    ApplyProfileGrade(*BoardActor, *CueFxSpawner);
    FTransform Xf;
    double Ms = 0.0;
    FString Cue;
    if (Mode == TEXT("dust")) {
      if (Parts.Num() < 4) return false;
      const FVector C = BoardModel.CellToWorld(FCString::Atoi(*Parts[1]), FCString::Atoi(*Parts[2]));
      Xf = S08FieldFx::DustTransform(C + FVector(0.0f, 0.0f, S08FieldFx::DustZ));
      Ms = Num(3, 0.0);
      Cue = TEXT("CUE-007");
    } else {
      const AS08FighterActor* A = Parts.IsValidIndex(1) ? BoardActor->FindFighterActor(Parts[1]) : nullptr;
      const AS08FighterActor* T = Parts.IsValidIndex(2) ? BoardActor->FindFighterActor(Parts[2]) : nullptr;
      if (!A || !T || !ChevronTransform(A->GetActorLocation(), T->GetActorLocation(), Xf)) return false;
      Ms = Num(3, 0.0);
      Cue = TEXT("CUE-008");
    }
    // spawned at the end of the warm-up (S08FxBenchFieldFinish(true)): the prewarm instances are gone by then
    GFieldBench.Spawns.Add({Cue, Xf, Ms});
    FS08Trace::Write(FString::Printf(TEXT("FX bench %s ms=%.0f queued"), *Mode, Ms));
    return true;
  }
  return false;
}

void AS08FlowGameMode::S08FxBenchFieldFinish(bool bWarmupDone) {
  if (!BoardActor) return;
  // the marks: the selection / combat state of the actors (the board's own refreshes after the build may clear it -
  // the bench re-applies everything at the end of the warm-up), then the static pose of each curve
  for (const TPair<FString, TMap<int32, double>>& Pair : GFieldBench.Marks) {
    AS08FighterActor* A = BoardActor->FindFighterActor(Pair.Key);
    if (!A) continue;
    const double* R = Pair.Value.Find(0);
    const double* T = Pair.Value.Find(1);
    if (R) A->SetSelected(true);
    if (T) A->SetCombatMarkers(false, true);
    A->SetFieldMarksBench(R != nullptr, R ? *R : 0.0, T != nullptr, T ? *T : 0.0);
  }
  if (US08MoveHighlightComponent* Hl = BoardActor->GetMoveHighlightMutable()) {
    for (const FFieldBench::FPulse& P : GFieldBench.Pulses) Hl->SetPulseStatic(P.Cell.X, P.Cell.Y, P.bTarget, P.Ms);
  }
  if (bWarmupDone) S08FxBenchCombatFinish();  // VS-6 F2: the star / heal bench systems
  if (bWarmupDone) S08FxBenchAbilityFinish();  // VS-6 F3: the ash / vortex / arc bench systems
  if (bWarmupDone && !GFieldBench.bSpawned && CueFxSpawner) {
    GFieldBench.bSpawned = true;
    ApplyProfileGrade(*BoardActor, *CueFxSpawner);
    for (const FFieldBench::FSpawn& S : GFieldBench.Spawns) {
      UNiagaraComponent* Comp = CueFxSpawner->Spawn(S.Cue, S.Xf);
      if (Comp) {
        // frozen at <ms>: the CPU simulation advanced in 1/60 s ticks, then paused (deterministic, FX-04)
        const int32 Ticks = FMath::Max(1, FMath::RoundToInt(S.Ms / (1000.0 / 60.0)));
        Comp->AdvanceSimulation(Ticks, 1.0f / 60.0f);
        Comp->SetPaused(true);
      }
      FS08Trace::Write(FString::Printf(TEXT("FX bench spawn cue=%s ms=%.0f result=%s"), *S.Cue, S.Ms,
                                       Comp ? TEXT("spawned") : TEXT("missing")));
    }
  }
  if (!GFieldBench.bDraftSet) return;
  GFieldBench.Draft.ViewerId = BenchViewerId;
  GFieldBench.Draft.Source = TEXT("bench");
  GFieldBench.Draft.bLeaderPips = BoardActor->DrawsLeaderPips();
  const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(BoardModel, Fighters, GFieldBench.Draft);
  BoardActor->SetMoveDraftView(View);
  FS08Trace::Write(FString::Printf(TEXT("FX bench plates candidates=%d pending=%d lastPaths=%d plates=%d choiceOnly=%d"),
                                   GFieldBench.Draft.CandidateFighterIds.Num(), GFieldBench.Draft.PendingCells.Num(),
                                   View.LastPaths.Num(), View.Plates.Num(),
                                   BoardActor->UsesChoiceLayer() ? 1 : 0));
}

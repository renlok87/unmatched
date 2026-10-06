// Z-1 «Фигуры» (ВР-Z1R-01, по делегированию): the figure hooks of the flow game mode, out of S08FlowGameMode.cpp (which
// keeps only the hook calls, the S08FlowGameModeUmHud.cpp pattern):
//   - AN-17 (ВР-17): the -BenchClipPose review stand - the pose list of the command line, the frozen poses, the shot
//     name and the per-figure screen rectangles (figrect) of every view;
//   - AN-24 / AN-25 (ВР-06): the facing adapters of the combat staging - Face turns the attacker to its target, Lunge
//     commits a turn deferred by reduced motion / speed "none" (ВР-Z1R-05), End returns an attacker that played no
//     clip; the board's game clock for the FACING traces.
#include "S08FlowGameMode.h"

#include "S08BoardActor.h"
#include "S08Facing.h"
#include "S08FighterActor.h"
#include "S08HeroesV2.h"
#include "S08TraceLog.h"
#include "GameFramework/PlayerController.h"
#include "Misc/Parse.h"

void AS08FlowGameMode::FiguresAttachBoard() {
  // F4: the FACING lines carry the CUE clock (t=), comparable with the 'CUE combat ... stage=lunge t=' lines.
  if (BoardActor) BoardActor->SetGameClock([this]() { return NowMs(); });
}

void AS08FlowGameMode::FiguresOnCombatEvent(const FS09CombatStageEvent& Event) {
  if (!BoardActor) return;
  const FS09CombatStageInput& In = CombatStage.GetInput();
  AS08FighterActor* Attacker = BoardActor->FindFighterActor(In.AttackerId);
  if (!Attacker) return;
  switch (Event.Type) {
    case ES09CombatEvent::Face: {
      // AN-24 (ВР-06): the attacker turns to the target over the remaining face window; a skipped pause puts the turn
      // with the clip's first 120 ms; Cut / catch-up never reach this event. Speed "none" (no clip) and reduced
      // motion defer it to the Lunge frame (ВР-Z1R-05).
      const AS08FighterActor* Target = BoardActor->FindFighterActor(In.TargetId);
      if (!Target) return;
      const int64 Gap = CombatStage.GetLungeMs() - Event.AtMs;
      const double Ms = Gap <= 0 ? S08Facing::AttackTurnMs : FMath::Min(static_cast<double>(Gap), S08Facing::AttackTurnMs);
      Attacker->PlayFaceTarget(In.TargetId, Target->GetActorLocation(), Ms, Event.AtMs,
                               /*bSnapAtLunge=*/CombatStage.LungePlayRate() <= 0.0f);
      return;
    }
    case ES09CombatEvent::Lunge:
      Attacker->CommitFaceTarget(Event.AtMs);
      return;
    case ES09CombatEvent::End:
      // AN-25: the return follows the end of the LungeAttack clip; an attacker that played none (speed "none", a
      // missing clip) still holds the target angle here - it returns with the end of the staging.
      if (Attacker->IsHoldingAttackFacing() && Attacker->GetHeroClip() != S08HeroesV2::EClip::LungeAttack &&
          Attacker->GetHeroClip() != S08HeroesV2::EClip::HitReact) {
        BoardActor->FighterReturnToRest(In.AttackerId, TEXT("attack-return"));
      }
      return;
    default:
      return;
  }
}

// ---- AN-17 (ВР-17): the -BenchClipPose review stand ---------------------------------------------------------------

bool AS08FlowGameMode::BenchParseClipPoses(const TCHAR* Cmd, TArray<S08HeroesV2::FBenchClipPoseSpec>& OutPoses,
                                           FString& InOutHeroId, int32 ViewCount) {
  OutPoses.Reset();
  // -BenchClipPose=<Clip>@<f1>,<f2>[;<Clip>@...]: every living v2 figure frozen at each pose x view. A bad list (or an
  // unknown -BenchClipPoseFighter) is traced and the bench runs without poses, exactly as before. The list is
  // comma-separated, so the value must not stop at a separator (FParse::Value would cut it at ',').
  FString ClipPoseText;
  if (!FParse::Value(Cmd, S08HeroesV2::BenchClipPoseParamName, ClipPoseText, /*bShouldStopOnSeparator=*/false) ||
      ClipPoseText.TrimStartAndEnd().IsEmpty()) {
    return false;
  }
  FString ClipPoseError;
  if (!S08HeroesV2::ParseBenchClipPoses(ClipPoseText, OutPoses, ClipPoseError)) {
    OutPoses.Reset();
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW clippose error=%s"), *ClipPoseError));
    return false;
  }
  FString WantedFighter;
  FParse::Value(Cmd, S08HeroesV2::BenchClipPoseFighterParamName, WantedFighter);
  if (!WantedFighter.IsEmpty()) {
    // <KingArthur|Merlin|Medusa|Harpy|id> (Harpy = the first harpy): the K2 views focus this fighter
    FString Resolved;
    for (const FS08BoardFighter& F : Fighters) {
      if (F.Id.Equals(WantedFighter, ESearchCase::IgnoreCase)) Resolved = F.Id;
    }
    for (const S08HeroesV2::FHeroSpec& Spec : S08HeroesV2::Specs()) {
      if (!Resolved.IsEmpty() || !WantedFighter.Equals(Spec.Key, ESearchCase::IgnoreCase)) continue;
      for (const FS08BoardFighter& F : Fighters) {
        if (F.IsAlive() && F.Name.Equals(Spec.FighterName, ESearchCase::IgnoreCase)) {
          Resolved = F.Id;
          break;
        }
      }
    }
    if (Resolved.IsEmpty()) {
      OutPoses.Reset();
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW clippose error=fighter '%s' not on this board"),
                                       *WantedFighter));
      return false;
    }
    InOutHeroId = Resolved;
  }
  FS08Trace::Write(FString::Printf(TEXT("BENCH clip-pose poses=%d views=%d fighter=%s"), OutPoses.Num(), ViewCount,
                                   *InOutHeroId));
  return OutPoses.Num() > 0;
}

int32 AS08FlowGameMode::BenchHoldClipPoses(const S08HeroesV2::FBenchClipPoseSpec& Spec, int32 PoseNumber,
                                           int32 PoseCount) {
  int32 Posed = 0;
  if (BoardActor) {
    for (const FS08BoardFighter& F : Fighters) {
      AS08FighterActor* Actor = BoardActor->FindFighterActor(F.Id);
      if (!Actor || !Actor->IsHeroV2() || !F.IsAlive()) continue;
      double T = 0.0, Len = 0.0, RootDeltaUU = 0.0;
      if (!Actor->BenchHoldClipPose(Spec, T, Len, RootDeltaUU)) continue;
      ++Posed;
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW clippose fighter=%s clip=%s frame=%d t=%.3f len=%.3f rootDeltaUU=%.2f"), *F.Id,
          S08HeroesV2::ClipName(Spec.Clip), FMath::RoundToInt(T * S08HeroesV2::ClipFps), T, Len, RootDeltaUU));
    }
  }
  FS08Trace::Write(FString::Printf(TEXT("BENCH clip-pose pose=%d/%d clip=%s posed=%d"), PoseNumber, PoseCount,
                                   S08HeroesV2::ClipName(Spec.Clip), Posed));
  return Posed;
}

FString AS08FlowGameMode::BenchClipPoseShotName(const FString& View, const S08HeroesV2::FBenchClipPoseSpec& Spec) {
  // bench-<view>-<clip>-f<NN>|-q<pct>-1920x1080.png
  const FString Token = Spec.bQuarter ? FString::Printf(TEXT("q%d"), Spec.Value) : FString::Printf(TEXT("f%02d"), Spec.Value);
  return FString::Printf(TEXT("bench-%s-%s-%s-1920x1080.png"), *View, S08HeroesV2::ClipName(Spec.Clip), *Token);
}

void AS08FlowGameMode::BenchTraceFigRects(const FString& View) {
  const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor) return;
  for (const FS08BoardFighter& F : Fighters) {
    const AS08FighterActor* Actor = BoardActor->FindFighterActor(F.Id);
    if (!Actor || !Actor->IsHeroV2()) continue;
    const FBox Box = Actor->GetV2FigureBox();
    if (!Box.IsValid) continue;
    FVector2D Min(TNumericLimits<float>::Max(), TNumericLimits<float>::Max());
    FVector2D Max(TNumericLimits<float>::Lowest(), TNumericLimits<float>::Lowest());
    bool bAny = false;
    for (int32 CX = 0; CX < 2; ++CX) {
      for (int32 CY = 0; CY < 2; ++CY) {
        for (int32 CZ = 0; CZ < 2; ++CZ) {
          const FVector Corner(CX ? Box.Max.X : Box.Min.X, CY ? Box.Max.Y : Box.Min.Y, CZ ? Box.Max.Z : Box.Min.Z);
          FVector2D Pixel(0.0f, 0.0f);
          if (PC->ProjectWorldLocationToScreen(Corner, Pixel, /*bPlayerViewportRelative=*/false)) {
            bAny = true;
            Min = Min.ComponentMin(Pixel);
            Max = Max.ComponentMax(Pixel);
          }
        }
      }
    }
    if (!bAny) continue;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW figrect fighter=%s view=%s x=%d y=%d w=%d h=%d"), *F.Id, *View,
        FMath::RoundToInt(Min.X), FMath::RoundToInt(Min.Y), FMath::RoundToInt(Max.X - Min.X),
        FMath::RoundToInt(Max.Y - Min.Y)));
  }
}

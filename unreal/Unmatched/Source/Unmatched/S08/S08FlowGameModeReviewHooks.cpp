// VC Frames (docs/game-design/evidence/VISUAL/VC/README.md, CLOSEOUT-2026-10-09 item 6): review-only hooks that make
// the live scenarios of the closing round happen in a random two-client match. Every hook needs -ArtPreview (the review
// flag, S08ArtLook::ReviewFlagName) on top of its own opt-in (an -S09Combat plan token or a flag) - the normal game never
// reaches them.
//
//   refuse         (plan token, ВР-VC-27) once per match, in the own maneuver draft: the hero is selected and the empty
//                  space nearest to it outside its reach tiers is clicked through the real move input (press + release:
//                  CUE-004, the FX-10 badge-refuse stamp, the why.* toast); the frame s09-fx10-refuse.png is taken 80 ms
//                  later (the stamp at rest 80...230 ms), the draft waits for the file (<= 12 s), then goes on as before.
//   sidekickfirst  (plan token, ВР-VC-28) every own living melee sidekick approaches the nearest enemy in the maneuver
//                  draft first, and the auto attack takes the sidekick attackers first; until the first sidekick attack
//                  (at most 10 own turns) the hero neither approaches nor attacks - the live harpy attack (AN-24);
//                  a harpy's lunge is framed 100 ms in (s09-an24-harpy-lunge.png, with -S08ExitShots / -S08FxShots).
//   -ArtPreviewHealProbe (ВР-VC-29) the decks of the demo heal only by The Holy Grail (King Arthur defends with it and
//                  ends the combat at <= 4 health - not within a demo match): the first STAGED combat damage of a living
//                  King Arthur hero (the Grail's own moment - an ability's damage shares its seq with the «−N» of the
//                  same frame, which keeps the «+N» out) is answered by ONE staged heal of the same amount through the
//                  FX-25 path (CUE-012 at the end of
//                  the staging, the motes, «+N» / the IC-49 «+» under reduced motion, the s09-fx25-heal.png hook
//                  frame). The server state is untouched: the HP of the HUD stays the server's.
#include "S08FlowGameMode.h"

#include "Fx/S08CombatFx.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08TraceLog.h"

bool AS08FlowGameMode::ReviewHooksOn() { return FParse::Param(FCommandLine::Get(), S08ArtLook::ReviewFlagName); }

bool AS08FlowGameMode::S09RefuseProbeStep(const FS08BoardFighter& Hero) {
  if (bS09RefuseDone || !ReviewHooksOn() || !BoardActor || !Flow.IsValid()) return false;
  if (S09RefuseShotAt < 0.0f) {
    const FS08Snapshot& Snap = Flow->GetAppliedSnapshot();
    CommandUi.SelectFighter(Hero.Id, Snap, BoardModel, Fighters);
    const FS09ReachTiers& Tiers = CommandUi.SelectedTiers;
    const FIntPoint Here(Hero.X, Hero.Y);
    const FVector HereW = BoardModel.CellToWorld(Hero.X, Hero.Y);
    FIntPoint Best(-1, -1);
    double BestD = TNumericLimits<double>::Max();
    for (const FS08Cell& C : BoardModel.Cells) {
      if (C.Type == ES08CellType::Unknown || !C.IsPassable()) continue;
      if (BoardModel.bHasTopology && !C.bHasLayout) continue;  // original maps: only a painted space is a space
      const FIntPoint P(C.X, C.Y);
      if (P == Here || (Tiers.bValid && (Tiers.BaseTier.Contains(P) || Tiers.BoostTier.Contains(P)))) continue;
      if (FS08BoardModel::FighterAt(Fighters, C.X, C.Y, FString())) continue;
      const double D = FVector::Dist2D(BoardModel.CellToWorld(C.X, C.Y), HereW);
      if (D < BestD) {
        BestD = D;
        Best = P;
      }
    }
    if (Best.X < 0) {
      bS09RefuseDone = true;
      FS08Trace::Write(TEXT("S09AUTO refuse probe skipped=no-space (review hook)"));
      return false;
    }
    MoveInput.OnPointerPressed(Best, FString());
    const FS09InputResult Result = MoveInput.OnPointerReleased(Best, FString(), CommandUi, Snap, BoardModel, Fighters);
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO refuse probe fighter=%s cell=%s handled=%d illegal=%d why=%s (review hook)"),
                                     *Hero.Id, *BoardModel.CellLabel(Best.X, Best.Y), Result.bHandled ? 1 : 0,
                                     Result.IllegalCell.X >= 0 ? 1 : 0,
                                     Result.Toast.IsSet() ? *Result.Toast.Key.ToString() : TEXT("-")));
    NoteTurnBoardInput(Best, FString(), Result);
    PlayBoardUiSound(Result, FString());
    S08FxBoardInput(Result, Best, FString());
    ApplyMoveInput(Result);
    S09RefuseShotAt = Elapsed + 0.08f;
    if (Result.IllegalCell.X < 0 || S09ShotDir.IsEmpty()) {
      bS09RefuseDone = true;
      return false;
    }
    return true;
  }
  if (S09RefuseShotPath.IsEmpty()) {
    if (Elapsed < S09RefuseShotAt || IsEvidenceCaptureBusy()) return true;
    S09RefuseShotPath = S09ShotDir / TEXT("s09-fx10-refuse.png");
    FS08Trace::Write(TEXT("S09AUTO refuse probe shot s09-fx10-refuse.png"));
    TakeEvidenceShot(S09RefuseShotPath);
    return true;
  }
  if (!FPaths::FileExists(S09RefuseShotPath) && Elapsed < S09RefuseShotAt + 12.0f) return true;
  bS09RefuseDone = true;
  return false;
}

void AS08FlowGameMode::S09SidekickApproach() {
  if (!Flow.IsValid()) return;
  const FS08Snapshot& Snap = Flow->GetAppliedSnapshot();
  TArray<FString> Ids;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.OwnerId != CommandUi.ViewerId || !Entry.IsAlive() || Entry.bIsHero) continue;
    if (FS09CommandUi::IsRangedAttacker(Entry)) continue;
    Ids.Add(Entry.Id);
  }
  for (const FString& Id : Ids) {
    const FS08BoardFighter* Entry = FindFighter(Id);
    if (!Entry) continue;
    FIntPoint Dest(-1, -1);
    int32 FromDist = 0, ToDist = 0, Steps = 0;
    if (!FS08BoardModel::PickApproachDestination(BoardModel, Fighters, Id, FS08BoardModel::FighterMovement(*Entry), Dest,
                                                 FromDist, ToDist, Steps)) {
      continue;
    }
    FString Reason;
    CommandUi.SelectFighter(Id, Snap, BoardModel, Fighters);
    const bool bOk = CommandUi.SetDestination(Id, Dest.X, Dest.Y, Snap, BoardModel, Fighters, Reason);
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO sidekick approach fighter=%s to=%s steps=%d enemyDist=%d->%d ok=%d%s%s"),
                                     *Id, *BoardModel.CellLabel(Dest.X, Dest.Y), Steps, FromDist, ToDist, bOk ? 1 : 0,
                                     bOk ? TEXT("") : TEXT(" why="), bOk ? TEXT("") : *Reason));
  }
}

bool AS08FlowGameMode::S09HoldHeroForSidekicks() const {
  if (bS09SidekickAttacked || OwnTurnIndex >= 10) return false;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.OwnerId == CommandUi.ViewerId && Entry.IsAlive() && !Entry.bIsHero && !FS09CommandUi::IsRangedAttacker(Entry)) {
      return true;
    }
  }
  return false;
}

void AS08FlowGameMode::S08HealProbeOnDamage(const FString& FighterId, int32 Damage, int32 Seq) {
  if (bS09HealProbeDone || Damage <= 0 || !ReviewHooksOn() ||
      !FParse::Param(FCommandLine::Get(), TEXT("ArtPreviewHealProbe"))) {
    return;
  }
  const FS08BoardFighter* F = FindFighter(FighterId);
  if (!F || !F->bIsHero || !F->IsAlive() || !F->Name.Contains(TEXT("Arthur"))) return;
  bS09HealProbeDone = true;
  FS08Trace::Write(FString::Printf(TEXT("FX heal probe fighter=%s amount=%d seq=%d hp=%d source=ArtPreviewHealProbe (review hook)"),
                                   *FighterId, Damage, Seq, F->Health));
  S08FxHealCue(FighterId, Damage, Seq);
}

void AS08FlowGameMode::S08An24LungeShot(const FString& AttackerId, int64 LungeAtMs) {
  if (!ReviewHooksOn() || !S08CombatFx::FxShotsRequested() || S09ShotDir.IsEmpty()) return;
  const FS08BoardFighter* F = FindFighter(AttackerId);
  if (!F || F->bIsHero || !(F->Name.Contains(TEXT("Harp")) || F->Label.Contains(TEXT("Harp")))) return;
  const FString Leaf(TEXT("s09-an24-harpy-lunge.png"));
  if (CombatFx.ShotsTaken.Contains(Leaf)) return;
  CombatFx.ShotsTaken.Add(Leaf);
  CombatFx.Shots.Add({Leaf, AttackerId, static_cast<double>(LungeAtMs) + 100.0});
  FS08Trace::Write(FString::Printf(TEXT("FXSHOT plan %s attacker=%s lunge=%lld"), *Leaf, *AttackerId,
                                   static_cast<long long>(LungeAtMs)));
}

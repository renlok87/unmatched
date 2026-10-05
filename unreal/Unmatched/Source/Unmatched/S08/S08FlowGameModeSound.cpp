// DE-032 (W-25; 02 SD-51, R-12; CUE-DISPATCHER.md §3.2): the UE adapter of the CUE sync-point sounds (S08CueSound.h).
// FS08CueSound decides when and how loud; this file plays the decision in the same frame as the visual event:
//   - ui:     the HUD press (HandleHudPressOutcome) and the board release (the MS-R-34 release path) - CUE-002/3/4;
//   - hit:    PresentHit - the contact boundary of the combat staging (or an unstaged hit's own frame) - CUE-011;
//   - step:   the edges of every CUE-007 plan, ticked right after the figures advance (TickFighterMoves);
//   - turn:   FeedTurnHud - the own turn only (CUE-015);
//   - result: the tick the result gate opens the screen (CUE-016).
// The assets come with DE-013 / ART-010 (cue-table sfx.sound null): until then every line is `result=fallback`, nothing
// plays and nothing is logged as an error. A path that is set but does not load is warned once and stays a fallback.
// The volumes (US08UserSettings, DE-025): master is the device's transient primary volume, the ambience volume is the
// class gain of a sound of class Ambience (the backdrop sound, none yet). Both apply when saved (OnChanged).
#include "S08FlowGameMode.h"

#include "AudioDevice.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "S08BoardActor.h"
#include "S08TraceLog.h"
#include "Sound/SoundBase.h"

DEFINE_LOG_CATEGORY_STATIC(LogS08CueSound, Log, All);

void AS08FlowGameMode::InitCueSound() {
  CueSound.AssetResolver = [this](const FString& SoftPath) -> FString {
    if (SoftPath.IsEmpty()) return FString();  // no bank variant: the fallback (D10)
    TObjectPtr<UObject>* Cached = CueSoundAssets.Find(SoftPath);
    if (!Cached) {
      USoundBase* Loaded = LoadObject<USoundBase>(nullptr, *SoftPath);
      if (!Loaded) UE_LOG(LogS08CueSound, Warning, TEXT("CUE sound %s did not load - fallback"), *SoftPath);
      Cached = &CueSoundAssets.Add(SoftPath, Loaded);
    }
    return *Cached ? S08SoundRows::ShortName(SoftPath) : FString();
  };
  ApplyAudioSettings(true);
}

void AS08FlowGameMode::ApplyAudioSettings(bool bStart) {
  TArray<FString> Lines;
  if (!CueSound.SetAudio(US08UserSettings::AudioNow(), NowMs(), bStart, Lines)) return;
  // Master is the whole output of this process (UI, SFX, music and the future backdrop sound) - one device volume.
  if (UWorld* World = GetWorld()) {
    if (FAudioDeviceHandle Device = World->GetAudioDevice()) {
      Device->SetTransientPrimaryVolume(CueSound.GetAudio().MasterGain());
    }
  }
  // At BeginPlay the trace file is not open yet: the line waits with the other boot lines (run D G-LIVE).
  for (const FString& Line : Lines) {
    if (bStart) {
      ArtHud.PendingTrace.Add(Line);
    } else {
      FS08Trace::Write(Line);
    }
  }
}

void AS08FlowGameMode::PlayCueSound(const FS08SoundRequest& Request) {
  TArray<FString> Lines;
  const FS08SoundDecision Decision = CueSound.Play(Request, NowMs(), Lines);
  WriteCueLines(Lines);
  if (Decision.Result != ES08SoundResult::Played) return;
  const TObjectPtr<UObject>* Asset = CueSoundAssets.Find(Decision.SoundPath);
  USoundBase* Sound = Asset ? Cast<USoundBase>(Asset->Get()) : nullptr;
  if (!Sound) return;
  // The concurrency of the row is the asset's USoundConcurrency (CUE-DISPATCHER.md §2); master is the device volume.
  UGameplayStatics::PlaySound2D(this, Sound, Decision.ClassGain, 1.0f, 0.0f, nullptr, nullptr, Decision.bUiSound);
}

void AS08FlowGameMode::PlayUiSound(const TCHAR* CueId, const FString& Subject) {
  NoteAudioInput();  // AU-S4: the idle line counts from the last input
  FS08SoundRequest Request;
  Request.Point = ES08SoundPoint::Ui;
  Request.CueId = CueId;
  Request.Subject = Subject;
  Request.Seq = Flow.IsValid() ? Flow->GetAppliedSnapshot().SequenceNumber : -1;
  Request.EventMs = NowMs();
  PlayCueSound(Request);
}

void AS08FlowGameMode::PlayBoardUiSound(const FS09InputResult& Result, const FString& FighterId) {
  const bool bRefused = Result.Toast.IsSet() || Result.IllegalCell.X >= 0;
  const bool bCommand = Result.bBeginManeuver || Result.bConfirmManeuver;
  const FS08BoardFighter* Fighter =
      FighterId.IsEmpty() ? nullptr
                          : Fighters.FindByPredicate([&FighterId](const FS08BoardFighter& F) { return F.Id == FighterId; });
  const bool bPickedOwn = Result.bSelectionChanged && Fighter && !Fighter->OwnerId.IsEmpty() &&
                          Fighter->OwnerId == ViewerIdNow();
  if (const TCHAR* Cue = S08SoundRows::BoardUiCue(bRefused, bCommand, bPickedOwn, Result.bSelectionChanged)) {
    PlayUiSound(Cue, FighterId);
  }
}

void AS08FlowGameMode::ScheduleStepSounds(const TArray<FS08MovePlan>& Plans) {
  TArray<FString> Lines;
  const int64 Now = NowMs();
  for (const FS08MovePlan& Plan : Plans) {
    if (!BoardActor || !BoardActor->FindFighterActor(Plan.FighterId)) continue;  // no figure on the board: nothing moves
    // CUE-007 jump_to_final: a new move of a figure lands its old one - the old edges are never shown
    CueSound.DropSteps(Now, TEXT("replace"), Lines, Plan.FighterId);
    CueSound.ScheduleSteps(Plan.FighterId, Plan.Seq, Now + static_cast<int64>(FMath::RoundToDouble(Plan.StartMs)),
                           Plan.StepMs, Plan.Steps, Plan.bSnapped);
  }
  WriteCueLines(Lines);
  TickStepSounds();  // the edges that start now (the first move of the seq) sound in this frame
}

void AS08FlowGameMode::TickStepSounds() {
  if (CueSound.PendingSteps() == 0) return;
  TArray<FS08StepSound> Due;
  CueSound.TakeDueSteps(NowMs(), Due);
  for (const FS08StepSound& Step : Due) {
    FS08SoundRequest Request;
    Request.Point = ES08SoundPoint::Step;
    Request.CueId = TEXT("CUE-007");
    Request.Subject = Step.FighterId;
    Request.Seq = Step.Seq;
    Request.EventMs = NowMs();  // the figure starts this edge in this frame (it advanced to NowMs just before)
    Request.Edge = Step.Edge;
    Request.Edges = Step.Edges;
    Request.DueMs = Step.DueMs;
    PlayCueSound(Request);
  }
}

void AS08FlowGameMode::PlayHitSound(const FString& FighterId, int32 Seq, int64 DueMs) {
  // AU-S4: the hit type of the attacker, one "multi" sound for the hits of one frame (TickAudioRuntime), the hurt
  // lines; HitReact and the tint start in this frame (PresentHit)
  AudioOnHit(FighterId, Seq, DueMs);
}

void AS08FlowGameMode::PlayTurnSound(int32 Seq, bool bOwnTurn) {
  FS08SoundRequest Request;
  Request.Point = ES08SoundPoint::Turn;
  Request.CueId = TEXT("CUE-015");
  Request.Seq = Seq;
  Request.EventMs = NowMs();  // the banner appears from the apply frame (DE-015)
  Request.bOwnTurn = bOwnTurn;
  PlayCueSound(Request);
  AudioOnTurn(bOwnTurn);  // AU-S4: the turn-start line (not on the first turn), the idle clock
}

void AS08FlowGameMode::PlayResultSting(int32 Seq, int64 ScreenMs) {
  FS08SoundRequest Request;
  Request.Point = ES08SoundPoint::Result;
  Request.CueId = TEXT("CUE-016");
  Request.Seq = Seq;
  Request.EventMs = ScreenMs;
  Request.BankId = AudioOnResult();  // AU-S4: the sting of the own hero and outcome; the theme leaves, the lines follow
  PlayCueSound(Request);
}

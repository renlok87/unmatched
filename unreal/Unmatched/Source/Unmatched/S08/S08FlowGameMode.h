// GD-029/030/031: BOOT -> LOGIN -> LOBBY -> ROOM -> BOARD grey flow.
// Phase 2 renders the authoritative board + fighters from the applied
// snapshot (GD-030) and drives gameplay commands through the single state
// store with an in-flight gate (GD-031). Packaged demo drive:
//   -S08Auto -S08Create (host) or -S08Code=XXXXXX (joiner),
//   -S08HeroId=<prisma id>, -S08Maneuver (auto maneuver when the board is
//   live and it is this client's turn), -S08Shot=<abs path> (1920x1080
//   HighResShot after the maneuver), -S08DropWsAfter=<seconds> (test hook:
//   abrupt WS loss mid-run to prove reconnect convergence),
//   -S08ExitAfter=<seconds>.
// Demo credentials NEVER travel on the process command line (visible to any
// local process listing): the driver injects them as the per-process
// environment variables S08_EMAIL / S08_PASSWORD.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "S08FlowController.h"
#include "S08BoardModel.h"
#include "S08FlowGameMode.generated.h"

class SEditableTextBox;
class STextBlock;
class SVerticalBox;
class AS08BoardActor;
class ACameraActor;

UCLASS()
class AS08FlowGameMode : public AGameModeBase {
  GENERATED_BODY()
public:
  AS08FlowGameMode();
  ~AS08FlowGameMode() override;
  virtual void BeginPlay() override;
  virtual void Tick(float DeltaSeconds) override;
  virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
  void BuildUi();
  void RefreshUi();
  void RunAutoDrive();
  void AutoAdvance();
  // ---- GD-030 board ----
  void HandleApplied(const FS08Snapshot& Snapshot, ES08SeqDecision Decision);
  void HandleCues(const TArray<FS08Cue>& Cues);
  void SyncBoardFromApplied();
  void SetupCameraForBoard();
  // ---- TASK-022 input ----
  void HandleClick();
  void SelectFighter(const FString& FighterId);
  void TryManeuverTo(int32 CellX, int32 CellY);
  void FinishPendingManeuver(int32 CellX, int32 CellY);
  // ---- demo drive ----
  void RunAutoManeuver();
  void TakeEvidenceShot();

  TUniquePtr<FS08FlowController> Flow;
  TWeakPtr<SEditableTextBox> EmailBox;
  TWeakPtr<SEditableTextBox> PasswordBox;
  TWeakPtr<SEditableTextBox> CodeBox;
  TWeakPtr<STextBlock> StatusLine;
  TWeakPtr<STextBlock> RoomLine;
  TWeakPtr<STextBlock> PlayersLine;
  TWeakPtr<STextBlock> ProblemLine;
  TWeakPtr<STextBlock> BoardLine;
  TWeakPtr<STextBlock> ToastLine;
  TSharedPtr<SVerticalBox> TraceBox;
  TArray<FString> TraceLines;

  UPROPERTY()
  TObjectPtr<AS08BoardActor> BoardActor;

  UPROPERTY()
  TObjectPtr<ACameraActor> BoardCamera;

  FS08BoardModel BoardModel;
  TArray<FS08BoardFighter> Fighters;
  FString SelectedFighterId;
  TSet<uint64> ReachableCells;
  FString Toast;
  float ToastUntil = 0.0f;
  float IllegalUntil = 0.0f;
  int32 ManeuverTargetX = -1;
  int32 ManeuverTargetY = -1;
  bool bAwaitManeuverFinish = false; // begin leg sent, waiting for pending id
  int32 ManeuverStartSeq = 0;
  float ShotAtElapsed = -1.0f;

  float PollAccumulator = 0.0f;
  float Elapsed = 0.0f;
  bool bAuto = false;
  bool bAutoCreate = false;
  bool bAutoManeuver = false;
  bool bShotTaken = false;
  bool bAutoManeuverDone = false;
  bool bSawCue = false; // joiner evidence shot trigger: an authoritative event arrived
  FString AutoEmail, AutoPassword, AutoCode, AutoHeroId, AutoShotPath;
  float AutoExitAfter = 0.0f;
  float AutoDropWsAfter = 0.0f; // >0: drop the live WS at this elapsed time
  bool bWsDroppedForTest = false;
  float AutoManeuverAfter = 0.0f; // >0: hold the auto maneuver until this elapsed time
  int32 AutoStep = 0;
  int32 AppliedCount = 0;
};

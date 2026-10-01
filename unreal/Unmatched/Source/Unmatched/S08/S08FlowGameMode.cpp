#include "S08FlowGameMode.h"
#include "S08BoardActor.h"
#include "S08FighterActor.h"
#include "S08Render.h"
#include "S08ArtHudText.h"
#include "S08ArtHudViews.h"
#include "S08ArtHudWidgets.h"
#include "S08Team.h"
#include "Blueprint/UserWidget.h"
#include "Misc/CoreDelegates.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/PlatformMisc.h"
#include "Misc/FileHelper.h"
#include "ImageUtils.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "InputKeyEventArgs.h"
#include "UnrealClient.h"
#include "Widgets/SViewport.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "S08TraceLog.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Text/STextBlock.h"
#include "Layout/Visibility.h"
#include "Styling/CoreStyle.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/Texture2D.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/SOverlay.h"
#include "DynamicRHI.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/GameUserSettings.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "RenderTimer.h"

namespace {
// ART-004 T1.1 (stage 3) opt-in live K2 measurements: per-client frame timing
// (-S08Perf), the camera-settled gate and the Head-socket projection at shot
// time. The state is file-local on purpose: no UCLASS header or reflection
// changes, so the generated registration code stays identical to the builds
// diagnosed in v3-live-hookup-diagnosis-2026-09-28.md (WITH_RELOAD A/B).
struct FS08ArtProbeState {
  bool bPerfInit = false;
  bool bPerf = false;
  bool bPerfConfigLogged = false;
  bool bPerfSummaryLogged = false;
  bool bCameraSettledLogged = false;
  float WindowStart = 0.0f;
  TArray<float> WindowFrameMs, WindowGpuMs, WindowGameMs, WindowRenderMs;
  TArray<float> RunFrameMs, RunGpuMs, RunGameMs, RunRenderMs;
  TArray<float> StartedFrameMs, StartedGpuMs, StartedGameMs, StartedRenderMs;
  // W4-C: frames with the art HUD plate on screen (UMG vs Slate delta GT);
  // alternate mode splits them by the visible implementation [0]=umg [1]=slate.
  TArray<float> ArtHudFrameMs, ArtHudGpuMs, ArtHudGameMs, ArtHudRenderMs;
  TArray<float> AltFrameMs[2], AltGpuMs[2], AltGameMs[2], AltRenderMs[2];
  // Steady frames of the CURRENT alternate period (paired per-period A/B).
  TArray<float> PeriodGameMs, PeriodGpuMs;
};
FS08ArtProbeState GS08ArtProbe;
constexpr float GS08PerfWarmupSeconds = 5.0f;
constexpr float GS08PerfWindowSeconds = 5.0f;

float S08PerfPercentile(TArray<float> Values, float Fraction) {
  if (Values.Num() == 0) return 0.0f;
  Values.Sort();
  const int32 Index = FMath::Clamp(FMath::CeilToInt(Fraction * Values.Num()) - 1, 0,
                                   Values.Num() - 1);
  return Values[Index];
}

float S08PerfMean(const TArray<float>& Values) {
  if (Values.Num() == 0) return 0.0f;
  double Sum = 0.0;
  for (const float V : Values) Sum += V;
  return static_cast<float>(Sum / Values.Num());
}

FString S08PerfStats(const TArray<float>& FrameMs, const TArray<float>& GpuMs,
                     const TArray<float>& GameMs, const TArray<float>& RenderMs) {
  const float MeanFrame = S08PerfMean(FrameMs);
  int32 Hitches = 0;
  float MaxFrame = 0.0f;
  for (const float V : FrameMs) {
    if (V > 50.0f) ++Hitches;
    MaxFrame = FMath::Max(MaxFrame, V);
  }
  return FString::Printf(
      TEXT("frames=%d fps=%.2f frameMs avg=%.2f p50=%.2f p95=%.2f p99=%.2f max=%.2f hitches50=%d ")
      TEXT("gpuMs avg=%.2f p50=%.2f p95=%.2f gameMs avg=%.2f p95=%.2f renderMs avg=%.2f p95=%.2f"),
      FrameMs.Num(), MeanFrame > 0.0f ? 1000.0f / MeanFrame : 0.0f, MeanFrame,
      S08PerfPercentile(FrameMs, 0.50f), S08PerfPercentile(FrameMs, 0.95f),
      S08PerfPercentile(FrameMs, 0.99f), MaxFrame, Hitches, S08PerfMean(GpuMs),
      S08PerfPercentile(GpuMs, 0.50f), S08PerfPercentile(GpuMs, 0.95f), S08PerfMean(GameMs),
      S08PerfPercentile(GameMs, 0.95f), S08PerfMean(RenderMs),
      S08PerfPercentile(RenderMs, 0.95f));
}

void S08WritePerfConfig() {
  const IConsoleVariable* MaxFps =
      IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"));
  const IConsoleVariable* VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync"));
  const UGameUserSettings* Settings = GEngine ? GEngine->GetGameUserSettings() : nullptr;
  FS08Trace::Write(FString::Printf(
      TEXT("PERF config tMaxFPS=%.1f frameRateLimit=%.1f vsync=%d smoothFrameRate=%d fixedFrameRate=%d rhi=%s"),
      MaxFps ? MaxFps->GetFloat() : -1.0f, Settings ? Settings->GetFrameRateLimit() : -1.0f,
      VSync ? VSync->GetInt() : -1, GEngine && GEngine->bSmoothFrameRate ? 1 : 0,
      GEngine && GEngine->bUseFixedFrameRate ? 1 : 0,
      GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none")));
}
} // namespace

AS08FlowGameMode::AS08FlowGameMode() {
  PrimaryActorTick.bCanEverTick = true;
  DefaultPawnClass = nullptr;
}

// Defined here so TUniquePtr<FS08FlowController> only needs the complete type
// in this translation unit (the header forward-declares it).
AS08FlowGameMode::~AS08FlowGameMode() = default;

void AS08FlowGameMode::BeginPlay() {
  Super::BeginPlay();

  FString HttpUrl;
  GConfig->GetString(TEXT("Unmatched.API"), TEXT("GraphQLUrl"), HttpUrl, GGameIni);
  // -S08Api override lets packaged/evidence runs target the worktree-local
  // backend without touching the committed ini default.
  FParse::Value(FCommandLine::Get(), TEXT("S08Api="), HttpUrl);
  // Same endpoint, ws scheme: the backend serves graphql-transport-ws on the
  // same /graphql route as HTTP POST.
  FString WsUrl = HttpUrl.Replace(TEXT("http://"), TEXT("ws://"));

  Flow = MakeUnique<FS08FlowController>(HttpUrl, WsUrl);
  ES08Stage PrevFlowStage = ES08Stage::Boot;
  Flow->OnStage.AddLambda([this, PrevFlowStage](ES08Stage Stage) mutable {
    OnStageChanged(PrevFlowStage, Stage);
    PrevFlowStage = Stage;
    RefreshUi();
  });
  Flow->OnRoom.AddLambda([this](const FS08RoomState& Room) {
    RefreshUi();
    // S10/GD-040: a terminal room row while the match is LIVE re-renders the
    // HUD even without a fresh snapshot - the interruption screen (ABORTED)
    // or the settled result screen must appear immediately.
    if (Flow.IsValid() && Flow->GetStage() == ES08Stage::Started) RefreshHud();
  });
  Flow->OnFlowError.AddLambda([this](const FS08GraphQLError& Error) {
    TraceLines.Add(TEXT("[error] ") + Error.Code + TEXT(": ") + Error.Message);
    // GD-038 (ACC-021): an expired session routes the player back to the
    // login screen - visible, no automatic retry anywhere.
    if (Error.Code == TEXT("SESSION_EXPIRED")) {
      Toast = TEXT("session expired - sign in again (F10 panel)");
      ToastUntil = Elapsed + 10.0f;
    }
    RefreshUi();
    RefreshHud();
  });
  Flow->OnLeaveFailed.AddLambda([this](const FS08GraphQLError& Error) {
    if (!bS09LobbyReturnSent) return;
    bS09LobbyReturnSent = false;
    bS09AutoLeaveRetryBlocked = true;
    Toast = TEXT("lobby return failed: ") + Error.Message + TEXT(" (press L to retry)");
    ToastUntil = Elapsed + 6.0f;
    FS08Trace::Write(TEXT("RESULT lobby-return failed: ") + Error.Code);
    RefreshHud();
  });
  Flow->OnCommandRejected.AddLambda([this](const FString& Tag, const FString& /*Reason*/) {
    // S10 review P1(5): a definitively rejected attack (the server ANSWERED -
    // e.g. the 401-then-refresh path - so the command is provably not
    // applied) must not leave the AttackDraft parked: S09AUTO returned on
    // every tick at the line below the plan while mode stayed AttackDraft.
    // Close the draft and count the bounded per-turn retry; the next tick
    // re-decides against fresh authoritative state.
    if (Tag != TEXT("ATTACK")) return;
    if (CommandUi.Mode != ES09CommandMode::AttackDraft) return;
    NextCommandAt = FS09AutoDraftTransitions::AttackDraftRejected(
        CommandUi.Mode, CommandUi.AttackAttackerId, CommandUi.AttackTargetId,
        CommandUi.AttackCardId, S09AttackAutoBudget, Elapsed);
    FS08Trace::Write(FString::Printf(
        TEXT("S09AUTO attack rejected by the server (%d/%d retries this turn) - draft reset; the command is never blindly resent"),
        S09AttackAutoBudget.Sends, S09AttackAutoBudget.Max));
    RefreshHud();
  });
  Flow->OnTrace.AddLambda([this](const FString& Line) {
    TraceLines.Add(Line);
    if (TraceLines.Num() > 200) TraceLines.RemoveAt(0, TraceLines.Num() - 200);
    FS08Trace::Write(Line);
    RefreshUi();
  });
  // GD-031: every applied/merged snapshot re-renders the authoritative board.
  Flow->OnApplied.AddUObject(this, &AS08FlowGameMode::HandleApplied);
  Flow->OnCues.AddUObject(this, &AS08FlowGameMode::HandleCues);

  BuildUi();
  // W5b-R: SHOT lines of the HUD layer at the END of the requesting frame (actual visibility + painted geometry) and
  // the pixel provenance of every capture (the engine hands the pixels to this delegate instead of writing the PNG).
  EndFrameHandle = FCoreDelegates::OnEndFrame.AddUObject(this, &AS08FlowGameMode::HandleEndFrame);
  ScreenshotCapturedHandle =
      UGameViewportClient::OnScreenshotCaptured().AddUObject(this, &AS08FlowGameMode::HandleScreenshotCaptured);

  // CLI: -S08Auto [-S08Create] [-S08HeroId=prisma-id]
  //      [-S08Maneuver] [-S08Shot=abs path] [-S08DropWsAfter=seconds]
  //      [-S08ExitAfter=seconds]. Login credentials come from the
  //      per-process environment (S08_EMAIL/S08_PASSWORD) and the joiner room
  //      code from S08_ROOM_CODE - NOT from the command line, where any local
  //      process listing could read them. -S08Code= stays as a manual
  //      (interactive) fallback only.
  bAuto = FParse::Param(FCommandLine::Get(), TEXT("S08Auto"));
  bAutoCreate = FParse::Param(FCommandLine::Get(), TEXT("S08Create"));
  bAutoManeuver = FParse::Param(FCommandLine::Get(), TEXT("S08Maneuver"));
  AutoEmail = FPlatformMisc::GetEnvironmentVariable(TEXT("S08_EMAIL"));
  AutoPassword = FPlatformMisc::GetEnvironmentVariable(TEXT("S08_PASSWORD"));
  AutoCode = FPlatformMisc::GetEnvironmentVariable(TEXT("S08_ROOM_CODE"));
  if (AutoCode.IsEmpty()) {
    FParse::Value(FCommandLine::Get(), TEXT("S08Code="), AutoCode);
  }
  FParse::Value(FCommandLine::Get(), TEXT("S08HeroId="), AutoHeroId);
  FParse::Value(FCommandLine::Get(), TEXT("S08Shot="), AutoShotPath);
  FParse::Value(FCommandLine::Get(), TEXT("S08DropWsAfter="), AutoDropWsAfter);
  FParse::Value(FCommandLine::Get(), TEXT("S08ManeuverAfter="), AutoManeuverAfter);
  FParse::Value(FCommandLine::Get(), TEXT("S08ExitAfter="), AutoExitAfter);
  if (FParse::Param(FCommandLine::Get(), TEXT("ArtPreview"))) {
    FParse::Value(FCommandLine::Get(), TEXT("ArtPreviewShotAfter="), ArtPreviewShotAfter);
    FParse::Value(FCommandLine::Get(), TEXT("ArtPreviewFocusZoom="), ArtPreviewFocusZoom);
    bArtPreviewSelectOwnHero = FParse::Param(
        FCommandLine::Get(), TEXT("ArtPreviewSelectOwnHero"));
  }
  // S10/GD-039: the auto host create mode (-S08Mode=VS_AI drives the packaged
  // one-client VS_AI gate; anything else stays ONE_V_ONE).
  {
    FString Mode;
    FParse::Value(FCommandLine::Get(), TEXT("S08Mode="), Mode);
    if (Mode == TEXT("VS_AI")) AutoCreateMode = TEXT("VS_AI");
  }
  // GD-033 demo drive: -S09Flow (host plan: zero-move, step, multi-fighter,
  // end turn, discard) / -S09Flow + -S09FlowBoost (joiner plan: boost the
  // freshly drawn card). -S09ShotDir=<abs> writes numbered evidence shots.
  bAutoS09 = FParse::Param(FCommandLine::Get(), TEXT("S09Flow"));
  bAutoS09Boost = FParse::Param(FCommandLine::Get(), TEXT("S09FlowBoost"));
  FParse::Value(FCommandLine::Get(), TEXT("S09ShotDir="), S09ShotDir);
  // S10/GD-040 opt-in packaged proof harness: -S10AbortProof arms the
  // interruption evidence drive (screen shot -> ONE leaveGame -> lobby shot
  // -> clean early exit). Without the flag the drive stays fully dormant -
  // the normal UI path never changes.
  bS10AbortProof = FParse::Param(FCommandLine::Get(), TEXT("S10AbortProof"));
  // GD-034 combat plan ('+'-separated tokens, works with -S09Flow; ',' is a
  // UE command-line value separator and truncates FParse::Value):
  //   attack    approach + attack with the first legal pair
  //   defend    pick the first legal defense card when the window opens
  //   nodefense defender closes the window with no card
  //   resolve   press resolve in COMBAT_RESOLVE
  //   scheme    play one scheme card in the next own action phase
  //   ranged    (opt-in, ENV-MAPS P5a) with 'attack': zone-only ranged picks
  //             first and never deferred for a may-boost card; ranged
  //             sidekicks maneuver to a zone-only (shared zone, no link) spot
  //   ownresult (opt-in, ENV-MAPS P5a) the combat-result shot only for a combat
  //             this seat attacked
  {
    FString Plan;
    FParse::Value(FCommandLine::Get(), TEXT("S09Combat="), Plan);
    if (!Plan.IsEmpty()) {
      Plan.ParseIntoArray(S09CombatPlan, TEXT("+"), true);
    }
  }
  // Backend-less packaged probe: fixture-driven HUD states + UI shots.
  FParse::Value(FCommandLine::Get(), TEXT("S09HudProbe="), S09ProbeDir);
  bS09Probe = !S09ProbeDir.IsEmpty();
  FParse::Value(FCommandLine::Get(), TEXT("S09ShotMode="), S09ShotMode);

  FS08Trace::Open();
  for (const FString& Line : ArtHud.PendingTrace) FS08Trace::Write(Line);
  ArtHud.PendingTrace.Reset();
  // W4-A: -S08RenderPreset=High (bench + evidence scripts) puts every sg.*
  // group on the acceptance reference before the first measured frame.
  {
    const FString Preset = S08ApplyRenderPresetFromCommandLine();
    if (!Preset.IsEmpty()) {
      FS08Trace::Write(FString::Printf(TEXT("RENDER preset applied=%s flag=S08RenderPreset"), *Preset));
    }
  }
  // W4-A -Bench: backend-less render bench (no login, no room, no HUD).
  bBench = FParse::Param(FCommandLine::Get(), TEXT("Bench"));
  if (bBench) {
    FS08Trace::Write(TEXT("BENCH start (W4-A backend-less render bench)"));
    RefreshUi();
    return;
  }
  if (bAutoS09 || bAutoS09Boost) {
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO config flow=%d boost=%d shotDir=%s"),
                                     bAutoS09 ? 1 : 0, bAutoS09Boost ? 1 : 0, *S09ShotDir));
  }
  if (bS10AbortProof) {
    FS08Trace::Write(TEXT("S10ABORTPROOF armed (opt-in packaged ABORTED harness)"));
  }
  if (bS09Probe) {
    FS08Trace::Write(FString::Printf(TEXT("S09PROBE start dir=%s shotMode=%s"),
                                     *S09ProbeDir,
                                     S09ShotMode.IsEmpty() ? TEXT("request") : *S09ShotMode));
    RefreshUi();
    return; // no backend drive in probe mode
  }
  UE_LOG(LogTemp, Display, TEXT("S08_FLOW_READY map=%s api=%s"), *GetWorld()->GetMapName(), *HttpUrl);
  TraceLines.Add(TEXT("BOOT"));
  if (bAuto) RunAutoDrive();
  RefreshUi();
}

void AS08FlowGameMode::RunAutoDrive() {
  // The room code itself is intentionally absent from this line: traces are
  // published evidence and must not carry joinable codes.
  TraceLines.Add(FString::Printf(TEXT("AUTO mode create=%d joinByCode=%s maneuver=%d"),
                                 bAutoCreate ? 1 : 0,
                                 AutoCode.IsEmpty() ? TEXT("no") : TEXT("yes"),
                                 bAutoManeuver ? 1 : 0));
  Flow->Login(AutoEmail, AutoPassword);
}

void AS08FlowGameMode::AutoAdvance() {
  if (!bAuto || !Flow.IsValid()) return;
  const ES08Stage Stage = Flow->GetStage();
  const FS08RoomState& Room = Flow->GetRoom();
  switch (Stage) {
    case ES08Stage::Login:
      // After login: host creates, joiner waits for the code from evidence
      // (operator passes -S08Code when starting the second client).
      Flow->FetchHeroes();
      if (bAutoCreate) {
        Flow->CreateRoom(AutoCreateMode);
        AutoStep = 1;
      } else if (!AutoCode.IsEmpty()) {
        Flow->JoinRoomByCode(AutoCode);
        AutoStep = 1;
      } else {
        Flow->EnterLobby(); // recovery path: myGames(LOBBY)
      }
      break;
    case ES08Stage::Room:
      if (AutoStep == 1) {
        // Room reached: pick hero pair from real content, then ready.
        const FString HeroId = AutoHeroId.IsEmpty()
                                   ? (Flow->GetHeroes().Num() > 0 ? Flow->GetHeroes()[0].Id : FString())
                                   : AutoHeroId;
        if (!HeroId.IsEmpty()) {
          Flow->SelectHero(HeroId);
          ++AutoStep;
        }
      } else if (AutoStep == 2) {
        Flow->ToggleReady();
        ++AutoStep;
      } else if (AutoStep == 3 && Room.IsHost(Flow->GetUserId())) {
        // S10/GD-039: a VS_AI room starts from ONE ready human seat - the
        // server bot takes the second seat inside startGame, so waiting for a
        // second human would never fire. PvP keeps the two-ready gate.
        if (Room.Mode == TEXT("VS_AI")) {
          const bool HumanReady =
              Room.Players.Num() == 1 && Room.Players[0].bIsReady &&
              !Room.Players[0].HeroId.IsEmpty();
          if (HumanReady) {
            Flow->StartGame();
            ++AutoStep;
          }
        } else {
          const bool AllReady = Room.Players.Num() == 2 &&
                                Room.Players[0].bIsReady && Room.Players[1].bIsReady;
          const bool BothHeroes = Room.Players.Num() == 2 && !Room.Players[0].HeroId.IsEmpty() &&
                                  !Room.Players[1].HeroId.IsEmpty();
          if (AllReady && BothHeroes) {
            Flow->StartGame();
            ++AutoStep;
          }
        }
      }
      break;
    case ES08Stage::Started:
      if (AutoStep == 4) {
        ++AutoStep;
        TraceLines.Add(TEXT("AUTO complete: room started, state stream attached"));
      } else if (AutoStep == 5 && bAutoManeuver && !bAutoManeuverDone && BoardActor &&
                 Flow->IsMyTurn() &&
                 (AutoManeuverAfter <= 0.0f || Elapsed >= AutoManeuverAfter)) {
        RunAutoManeuver();
      }
      break;
    default:
      break;
  }
}

// ---- GD-030 board rendering ---------------------------------------------

void AS08FlowGameMode::HandleApplied(const FS08Snapshot& Snapshot, ES08SeqDecision Decision) {
  ++AppliedCount;
  FS08Trace::Write(FString::Printf(TEXT("HANDLE_APPLIED #%d seq=%d decision=%d fightersValid=%d boardValid=%d"),
      AppliedCount, Snapshot.SequenceNumber, static_cast<int32>(Decision),
      Snapshot.Fighters.IsValid() ? 1 : 0, Snapshot.BoardState.IsValid() ? 1 : 0));
  TrackCombatResult(Snapshot, Decision);
  // ---- GD-032/033: feed the HUD model and the command-state machine ----
  const FString ViewerId = Flow.IsValid() ? Flow->GetUserId() : FString();
  if (!ViewerId.IsEmpty()) {
    CommandUi.ViewerId = ViewerId;
    CommandUi.bCommandInFlight = Flow->IsManeuverInFlight();
    const ES09CommandMode OldMode = CommandUi.Mode;
    if (FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters) &&
        CommandUi.OnSnapshot(Snapshot, BoardModel, Fighters)) {
      const TCHAR* ModeName = CommandUi.Mode == ES09CommandMode::ManeuverDraft
                                  ? TEXT("MANEUVER-DRAFT")
                                  : CommandUi.Mode == ES09CommandMode::DiscardDraft
                                        ? TEXT("DISCARD-DRAFT")
                                        : TEXT("closed");
      FString Line = FString::Printf(TEXT("%s mode=%s"), ModeName,
                                     CommandUi.Mode == ES09CommandMode::ManeuverDraft
                                         ? *CommandUi.PendingManeuverId
                                         : TEXT(""));
      if (CommandUi.Mode == ES09CommandMode::DiscardDraft) {
        Line = FString::Printf(TEXT("DISCARD-DRAFT count=%d pending=%s"),
                               CommandUi.PendingDiscard.Count,
                               *CommandUi.PendingDiscard.Id);
      }
      TraceLines.Add(Line);
      FS08Trace::Write(Line);
      if (OldMode == ES09CommandMode::None &&
          CommandUi.Mode == ES09CommandMode::ManeuverDraft) {
        // The server draw is committed: beginManeuver MUST NOT be re-sent.
        FS08Trace::Write(TEXT("DRAFT-OPEN draw committed (resume instead of begin)"));
      }
    }
    Hud.Build(Snapshot, ViewerId, PreviousOwnHandIds, Flow->GetDecksSeq(),
              Flow->GetDiscardPilesSeq());
    FS08Trace::Write(FString::Printf(TEXT("MODE seq=%d mode=%d combat=%d pending=%d"),
        Snapshot.SequenceNumber, static_cast<int32>(CommandUi.Mode),
        CommandUi.Combat.bPresent ? 1 : 0, CommandUi.bHasPendingChoice ? 1 : 0));
    // GD-036: one RESULT trace line per authoritative seq - an equal-seq
    // merge (WS push + HTTP refetch of the terminal body) never re-logs.
    if (Hud.bGameOver && Snapshot.SequenceNumber != S09ResultTraceSeq) {
      S09ResultTraceSeq = Snapshot.SequenceNumber;
      FS08Trace::Write(FString::Printf(TEXT("RESULT seq=%d outcome=%s winner=%s"),
          Snapshot.SequenceNumber, *Hud.OutcomeWord(),
          Hud.bWinnerKnown ? *Hud.WinnerHeroName : TEXT("(none)")));
    }
    FS08Trace::Write(Hud.SummaryLine());
    // GD-036: the result screen presents only the server verdict. A gameplay
    // action toast set seconds before GAME_OVER (3-5s TTL) would still be
    // live at the 2s-settled result capture and render over the panel.
    if (Hud.bGameOver && !Toast.IsEmpty()) {
      Toast.Reset();
      ToastUntil = 0.0f;
    }
    // Refresh the previous-hand baseline only in a QUIET state: while a
    // draft (own maneuver/discard) is open the freshly drawn card must stay
    // flagged *new* across WS push + HTTP refetch re-applies of the same
    // state, or the boost pick loses it before the confirm.
    if (Snapshot.HandZones.IsValid() && CommandUi.Mode == ES09CommandMode::None &&
        Snapshot.SequenceNumber != PreviousHandSeq) {
      PreviousHandSeq = Snapshot.SequenceNumber;
      PreviousOwnHandIds.Reset();
      if (const FS09PlayerPanel* Own = Hud.ViewerPanel()) {
        for (const FS09CardView& Card : Own->Cards) {
          PreviousOwnHandIds.Add(Card.InstanceId);
        }
      }
    }
    RefreshHud();
  }
  if (!FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters)) {
    FS08Trace::Write(TEXT("BOARD: fighters projection missing - board not rendered"));
    return;
  }
  if (!BoardModel.Decode(Snapshot.BoardState)) {
    FS08Trace::Write(TEXT("BOARD: boardState undecodable - board not rendered"));
    return;
  }
  SyncBoardFromApplied();
}

void AS08FlowGameMode::TrackCombatResult(const FS08Snapshot& Snapshot,
                                         ES08SeqDecision Decision) {
  // Combat close = an APPLIED transition from a combat phase to a non-combat
  // phase (same-seq merges must not re-freeze the result - ACC-011).
  const bool bPrevCombat = bHasPrevApplied &&
                           (PrevApplied.Phase == TEXT("COMBAT") ||
                            PrevApplied.Phase == TEXT("COMBAT_RESOLVE"));
  const bool bNowCombat =
      Snapshot.Phase == TEXT("COMBAT") || Snapshot.Phase == TEXT("COMBAT_RESOLVE");
  const FS08Snapshot Baseline = PrevApplied; // copy before the bookkeeping
  if (Decision == ES08SeqDecision::Apply && !bPrevCombat && bNowCombat) bCombatLungeSent = false;
  // Wave 5c-B: the attacker lunges when the combat resolves (a no-op without -ArtPreviewHeroesV2).
  if (Decision == ES08SeqDecision::Apply && Snapshot.Phase == TEXT("COMBAT_RESOLVE") && !bCombatLungeSent &&
      BoardActor) {
    FS08CombatInfo Resolving;
    if (FS08Contracts::CombatInfo(Snapshot, Resolving) && !Resolving.AttackerId.IsEmpty()) {
      bCombatLungeSent = true;
      BoardActor->NotifyFighterAnimEvent(Resolving.AttackerId, S08HeroesV2::EEvent::Attack,
                                         Snapshot.SequenceNumber);
    }
  }
  if (Decision == ES08SeqDecision::Apply && !bPrevCombat && bNowCombat) {
    CombatStartTargetId.Reset();
    CombatStartTargetHealth = -1;
    FS08CombatInfo OpeningCombat;
    TArray<FS08BoardFighter> OpeningFighters;
    // A client can first subscribe after ATTACK opened COMBAT. That initial
    // COMBAT snapshot is still pre-resolution, so its target HP is a valid
    // starting observation; COMBAT_RESOLVE alone is not (damage may exist).
    const TSharedPtr<FJsonValue>& OpeningSource = bHasPrevApplied
        ? Baseline.Fighters : Snapshot.Fighters;
    if ((bHasPrevApplied || Snapshot.Phase == TEXT("COMBAT")) &&
        FS08Contracts::CombatInfo(Snapshot, OpeningCombat) &&
        FS08BoardModel::DecodeFighters(OpeningSource, OpeningFighters)) {
      CombatStartTargetId = OpeningCombat.TargetFighterId;
      for (const FS08BoardFighter& Fighter : OpeningFighters) {
        if (Fighter.Id == CombatStartTargetId) {
          CombatStartTargetHealth = Fighter.Health;
          break;
        }
      }
    }
  }
  if (Decision == ES08SeqDecision::Apply) {
    PrevApplied = Snapshot;
    bHasPrevApplied = true;
  }
  if (!(Decision == ES08SeqDecision::Apply && bPrevCombat && !bNowCombat)) return;

  FS08CombatInfo PrevCombat;
  const bool bHadCombat = FS08Contracts::CombatInfo(Baseline, PrevCombat);
  if (bHadCombat && !bCombatLungeSent && BoardActor && !PrevCombat.AttackerId.IsEmpty()) {
    BoardActor->NotifyFighterAnimEvent(PrevCombat.AttackerId, S08HeroesV2::EEvent::Attack, Snapshot.SequenceNumber);
  }
  bCombatLungeSent = false;
  if (!bHadCombat) {
    CombatStartTargetId.Reset();
    CombatStartTargetHealth = -1;
    return;
  }

  // Damage can be applied on an earlier COMBAT_RESOLVE event. Compare the
  // public target HP at combat opening with the first non-combat snapshot,
  // not just the closing transition. Reconnects without an opening baseline
  // remain unknown rather than being falsely reported as zero.
  TArray<FS08BoardFighter> NewFighters;
  FS08BoardModel::DecodeFighters(Snapshot.Fighters, NewFighters);
  int32 Damage = -1;
  const FS08BoardFighter* Target = nullptr;
  for (const FS08BoardFighter& New : NewFighters) {
    if (New.Id != PrevCombat.TargetFighterId) continue;
    Target = &New;
    if (CombatStartTargetId == New.Id && CombatStartTargetHealth >= 0) {
      Damage = FMath::Max(0, CombatStartTargetHealth - New.Health);
    }
    break;
  }
  CombatStartTargetId.Reset();
  CombatStartTargetHealth = -1;
  LastCombatResult = FS09CombatResult();
  LastCombatResult.bValid = true;
  LastCombatResult.SequenceNumber = Snapshot.SequenceNumber;
  LastCombatResult.Damage = Damage;
  LastCombatResult.TargetFighterId = PrevCombat.TargetFighterId;
  const FString ViewerId = Flow.IsValid() ? Flow->GetUserId() : FString();
  LastCombatResult.bViewerWasDefender = PrevCombat.DefenderId == ViewerId;
  LastCombatResult.bViewerWasAttacker = !LastCombatResult.bViewerWasDefender;
  if (LastCombatResult.bViewerWasDefender && PrevCombat.bHasDefenseValue) {
    LastCombatResult.OwnCommittedValue = PrevCombat.DefenseValue;
  } else if (LastCombatResult.bViewerWasAttacker && PrevCombat.bHasAttackValue) {
    LastCombatResult.OwnCommittedValue = PrevCombat.AttackValue + PrevCombat.BoostValue;
  }
  const TCHAR* ResultRole = LastCombatResult.bViewerWasDefender ? TEXT("defended") : TEXT("attacked");
  LastCombatResult.OutcomeLine = FString::Printf(
      TEXT("COMBAT OVER (seq %d): you %s%s - %s"),
      Snapshot.SequenceNumber, ResultRole,
      LastCombatResult.OwnCommittedValue >= 0
          ? *FString::Printf(TEXT(" with value %d"), LastCombatResult.OwnCommittedValue)
          : TEXT(""),
      Damage >= 0
          ? *FString::Printf(TEXT("%s took %d damage"),
                            Target ? *Target->Label : TEXT("the target"), Damage)
          : TEXT("damage unavailable after reconnect"));
  LastCombatResult.ShownAt = Elapsed;
  FS08Trace::Write(FString::Printf(TEXT("COMBAT-RESULT seq=%d damage=%d role=%s"),
                                   Snapshot.SequenceNumber, LastCombatResult.Damage, ResultRole));
  // W5b-R: a combat whose damage CUE arrived before its combat state (reconnect / merged snapshots): take the combat
  // damage frame if the target's number is still alive and belongs to this combat (<= 2 snapshots before the result).
  if (BoardActor && BoardActor->IsArtActive() && ArtHud.bTagsEnabled && !bS09ShotDamageCombat &&
      DamageCombatShotAtElapsed < 0.0f && !S09ShotDir.IsEmpty()) {
    const int32 NumberSeq = BoardActor->GetDamageNumberSeq(LastCombatResult.TargetFighterId);
    if (NumberSeq >= 0 && NumberSeq >= Snapshot.SequenceNumber - 2) {
      DamageCombatShotAtElapsed = Elapsed + 0.2f;
      DamageCombatShotDeadline = Elapsed + 0.8f;
      FS08Trace::Write(FString::Printf(
          TEXT("S09AUTO damage-combat scheduled fighter=%s seq=%d resultSeq=%d source=combat-result"),
          *LastCombatResult.TargetFighterId, NumberSeq, Snapshot.SequenceNumber));
    }
  }
  // ENV-MAPS P5a opt-in plan token 'ownresult' (run-combat-demo -JoinerAttack host plan): the combat-result evidence
  // shot waits for a combat THIS seat attacked. As a defender the host's result panel can be replaced in the very
  // next frame by its own post-combat pending choice (Medusa TARGET_FIGHTER), which the result gate rejects.
  const bool bResultShotRoleOk = !S09CombatPlan.Contains(TEXT("ownresult")) || LastCombatResult.bViewerWasAttacker;
  if (!S09ShotDir.IsEmpty() && !bS09ShotResult && bResultShotRoleOk) {
    bS09ShotResult = true;
    S09ShotResultPath = S09ShotDir / TEXT("s09-combat-result.png");
    ShotResultAtElapsed = Elapsed;
    FS08Trace::Write(TEXT("S09AUTO combat-result shot"));
    TakeEvidenceShot(S09ShotResultPath);
  }
  RefreshHud();
}

void AS08FlowGameMode::SyncBoardFromApplied() {
  // W4-A -Bench has no room: the fixture names the board row and the viewer.
  const FString RoomBoardId = bBench ? BenchBoardId : Flow->GetRoom().BoardId;
  const FString ViewerId = bBench ? BenchViewerId : Flow->GetUserId();
  if (!BoardActor) {
    FActorSpawnParameters Params;
    Params.Owner = this;
    BoardActor = GetWorld()->SpawnActor<AS08BoardActor>(
        AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, Params);
    if (BoardActor) {
      // T3.2: the room's Board row id selects the -ArtPreview board profile.
      BoardActor->SetRoomBoardId(RoomBoardId);
      BoardActor->Rebuild(BoardModel);
      SetupCameraForBoard();
      // INT-019 control points (evidence line, also asserted by automation
      // tests against the same formula).
      const FVector CornerA = BoardModel.CellToWorld(0, 0);
      const FVector CornerB = BoardModel.CellToWorld(BoardModel.Width - 1, BoardModel.Height - 1);
      const FVector NeighborA = BoardModel.CellToWorld(BoardModel.Width / 2, BoardModel.Height / 2);
      const FVector NeighborB = BoardModel.CellToWorld(BoardModel.Width / 2, BoardModel.Height / 2 + 1);
      const FString Line = FString::Printf(
          TEXT("BOARD %dx%d cells | control points: (0,0)=(%.0f,%.0f,%.0f) (%d,%d)=(%.0f,%.0f,%.0f) | neighbor pair (dist %.0f uu)"),
          BoardModel.Width, BoardModel.Height, CornerA.X, CornerA.Y, CornerA.Z,
          BoardModel.Width - 1, BoardModel.Height - 1, CornerB.X, CornerB.Y, CornerB.Z,
          FVector::Dist(NeighborA, NeighborB));
      TraceLines.Add(Line);
      FS08Trace::Write(Line);
      if (BoardModel.bHasTopology) {
        // ENV-MAPS evidence: the client plays this board on its link graph.
        int32 Spaces = 0, LinkEnds = 0;
        FString Starts;
        for (int32 Y = 0; Y < BoardModel.Height; ++Y) {
          for (int32 X = 0; X < BoardModel.Width; ++X) {
            const FS08Cell* Cell = BoardModel.CellAt(X, Y);
            if (!Cell || !Cell->bHasLayout) continue;
            ++Spaces;
            LinkEnds += BoardModel.Neighbours(FIntPoint(X, Y)).Num();
            if (Cell->StartSlot > 0) {
              Starts += FString::Printf(TEXT("%s%d:%s"), Starts.IsEmpty() ? TEXT("") : TEXT(","),
                                        Cell->StartSlot, *BoardModel.CellLabel(X, Y));
            }
          }
        }
        const FS08LayoutFrame& Frame = BoardModel.LayoutFrame;
        const FString TopologyLine = FString::Printf(
            TEXT("BOARD topology spaces=%d links=%d starts=%s frame=%.0fx%.0fpx uuPerPx=%.4f radius=%.1fuu (%s)"),
            Spaces, LinkEnds / 2, Starts.IsEmpty() ? TEXT("-") : *Starts, Frame.SrcSize.X,
            Frame.SrcSize.Y, Frame.UuPerPx, Frame.SpaceRadiusUU(),
            Frame.bSet ? TEXT("profile") : TEXT("default"));
        TraceLines.Add(TopologyLine);
        FS08Trace::Write(TopologyLine);
      }
    }
  } else {
    BoardActor->SetRoomBoardId(RoomBoardId);
    BoardActor->Rebuild(BoardModel);
  }
  if (BoardActor) {
    // W5b-R D-2: absolute teams by the room seat order (P1 = seat 0 / host); the bench has no room (fighter prefix).
    {
      const FString P1Owner = (!bBench && Flow.IsValid())
          ? S08TeamP1OwnerId(Flow->GetRoom().Players, Flow->GetRoom().HostId) : FString();
      const ES08TeamColorMode Mode = static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode);
      BoardActor->SetTeamMapping(P1Owner, Mode);
      TArray<FString> P1, P2;
      for (const FS08BoardFighter& F : Fighters) {
        (BoardActor->TeamOfFighter(F) == ES08TeamSlot::P1 ? P1 : P2).Add(F.Id);
      }
      const FString Mapping = FString::Printf(
          TEXT("ARTPREVIEW team mapping mode=%s source=%s viewerTeam=%s p1=%s p2=%s"), S08TeamColorModeName(Mode),
          bBench ? TEXT("fighter-prefix") : (Flow.IsValid() && Flow->GetRoom().Players.Num() > 0 ? TEXT("seatOrder")
                                                                                              : TEXT("host")),
          P1Owner.IsEmpty() ? TEXT("-") : (P1Owner == ViewerId ? TEXT("P1") : TEXT("P2")),
          *FString::Join(P1, TEXT(",")), *FString::Join(P2, TEXT(",")));
      if (Mapping != LastTeamMappingLine) {
        LastTeamMappingLine = Mapping;
        FS08Trace::Write(Mapping);
      }
    }
    BoardActor->SyncFighters(BoardModel, Fighters, ViewerId);
    SyncCombatFocus();
    // GD-030 six-fighter evidence line: the projection's roster, split into
    // own/enemy for THIS viewer (asserted by the demo driver; the image
    // checker alone cannot count silhouettes).
    int32 Alive = 0, Own = 0, Enemy = 0;
    for (const FS08BoardFighter& F : Fighters) {
      if (!F.IsAlive()) continue;
      ++Alive;
      if (F.OwnerId == ViewerId) ++Own; else ++Enemy;
    }
    FS08Trace::Write(FString::Printf(TEXT("FIGHTERS synced n=%d alive=%d own=%d enemy=%d"),
                                     Fighters.Num(), Alive, Own, Enemy));
    // Selection survived the update: recompute reachability from fresh data.
    // In a GD-033 maneuver draft the draft's own selection (with boost
    // allowance) wins over the plain board selection; in a GD-035 pending
    // draft the pending fighter + its legal cells win.
    if (CommandUi.Mode == ES09CommandMode::PendingChoice &&
        (!CommandUi.PendingFighterId.IsEmpty() || CommandUi.PendingCells.Num() > 0)) {
      BoardActor->SetSelectedFighter(CommandUi.PendingFighterId, CommandUi.PendingCells);
    } else if (CommandUi.Mode == ES09CommandMode::ManeuverDraft &&
        !CommandUi.SelectedFighterId.IsEmpty()) {
      BoardActor->SetSelectedFighter(CommandUi.SelectedFighterId, CommandUi.ReachableCells);
    } else if (!SelectedFighterId.IsEmpty()) {
      SelectFighter(SelectedFighterId);
    }
  }
  RefreshUi();
}

void AS08FlowGameMode::SyncCombatFocus() {
  if (!BoardActor || !Flow.IsValid()) return;
  if (CommandUi.Combat.bPresent &&
      (Flow->GetAppliedSnapshot().Phase == TEXT("COMBAT") ||
       Flow->GetAppliedSnapshot().Phase == TEXT("COMBAT_RESOLVE"))) {
    BoardActor->SetCombatFocus(CommandUi.Combat.AttackerId,
                               CommandUi.Combat.TargetFighterId);
  } else if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
    BoardActor->SetCombatFocus(CommandUi.AttackAttackerId,
                               CommandUi.AttackTargetId);
  } else {
    BoardActor->SetCombatFocus(FString(), FString());
  }
}

void AS08FlowGameMode::SetupCameraForBoard() {
  if (!GetWorld()) return;
  // Fit the whole board (any W/H) at FOV 35, pitch -55, yaw -90 (INT-019:
  // camera looks along -Y, row y=0 far/north). UE's FOVAngle is the
  // HORIZONTAL fov: derive the vertical half-tan by dividing by the aspect
  // (treating it as vertical shrinks the real vertical fov to ~20 degrees
  // and the near board corner with its fighters falls out of frame).
  const float Hfov = 35.0f;
  // ENV-MAPS (ENV-O10): the same K1 formula (S08K1FitDistanceUU: margin 60, x1.12) on the board half extent:
  // a topology board frames its map canvas (the active map-image profile's map, 891.333 x 577.333 uu at 2/3 uu
  // per px -> 1872 uu), never the W x H lattice of the topology contract; a grid keeps W x H x 50 (1931 uu on
  // Cobble 5x6, bit for bit).
  const FVector2D BoardHalf = BoardActor ? BoardActor->GetBoardHalfExtentUU() : S08BoardHalfExtentUU(BoardModel);
  const float SinPitch = FMath::Sin(FMath::DegreesToRadians(55.0f));
  const float CosPitch = FMath::Cos(FMath::DegreesToRadians(55.0f));
  // ENV-U9 (user decision 2026-09-30, "move back to ~x1.25"): the overview = the fit x the active board profile's
  // k1DistanceMul - 1.25 on the two map-image boards (1872.2 -> 2340.2 uu: the colonnade / ship and the sides of the
  // diorama are in K1), 1 everywhere else (grids bit for bit, the grey topology view of a refused map profile).
  // The zoom rig takes both: its ratios (follow-from, focus zoom, label ratio) are relative to the overview, its far
  // limit stays fit / OverviewOutRatio (2880.2 uu on the maps, one wheel notch out), its near limit 300 uu.
  const float Fit = S08K1FitDistanceUU(BoardHalf);
  const float K1Mul = BoardActor ? BoardActor->GetK1DistanceMul() : 1.0f;
  const float Distance = S08K1OverviewDistanceUU(Fit, K1Mul);
  const FVector Location(0.0f, Distance * CosPitch, Distance * SinPitch);
  if (BoardModel.bHasTopology) {
    FS08Trace::Write(FString::Printf(TEXT("CAMERA extents source=%s half=%.1fx%.1f dist=%.1f fit=%.1f k1Mul=%.3f"),
                                     BoardActor && BoardActor->IsMapImageActive() ? TEXT("map-image") : TEXT("map-canvas"),
                                     BoardHalf.X, BoardHalf.Y, Distance, Fit, K1Mul));
  }
  // ART-004 T2.2: zoom parameters from one config (defaults <- game ini
  // [Unmatched.Camera] <- -S08Camera*= overrides), traced once per board.
  CameraZoom.Config = FS08CameraZoomConfig();
  CameraZoom.Config.ApplyIni(GGameIni);
  CameraZoom.Config.ApplyCommandLine(FCommandLine::Get());
  CameraZoom.Config.Sanitize();
  CameraZoom.Reset(Distance, Fit);

  if (!BoardCamera) {
    FActorSpawnParameters Params;
    Params.Owner = this;
    BoardCamera = GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), Location,
                                                       FRotator(-55.0f, -90.0f, 0.0f), Params);
    BoardCamera->GetCameraComponent()->SetFieldOfView(Hfov);
    if (auto* PC = GetWorld()->GetFirstPlayerController()) {
      PC->SetViewTarget(BoardCamera);
      PC->bShowMouseCursor = true;
    }
  } else {
    BoardCamera->SetActorLocationAndRotation(Location, FRotator(-55.0f, -90.0f, 0.0f));
  }
  const FString Line = FString::Printf(TEXT("CAMERA dist=%.0f loc=(%.0f,%.0f,%.0f) pitch=-55 yaw=-90"),
                                       Distance, Location.X, Location.Y, Location.Z);
  TraceLines.Add(Line);
  FS08Trace::Write(Line);
  FS08Trace::Write(FString::Printf(
      TEXT("CAMERA config overview=%.1f nearest=%.1f farthest=%.1f zoomRange=%.2f-%.2f fit=%.1f k1Mul=%.3f %s"),
      CameraZoom.Overview, CameraZoom.MinDistance(), CameraZoom.MaxDistance(),
      CameraZoom.ZoomOf(CameraZoom.MaxDistance()), CameraZoom.ZoomOf(CameraZoom.MinDistance()), CameraZoom.Fit,
      K1Mul, *CameraZoom.Config.Describe()));
}

void AS08FlowGameMode::UpdateBoardCamera(float DeltaSeconds) {
  if (!BoardCamera || !CameraZoom.IsReady()) return;
  auto* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (PC && Flow.IsValid() && Flow->GetStage() == ES08Stage::Started &&
      !Hud.bGameOver) {
    // D-10: wheel changes distance only; the perspective, pitch and yaw stay
    // fixed. Limits/step/animation come from FS08CameraZoomConfig (Q-302
    // proposals); every OS event is traced INPUT ... src=os + CAMERA ....
    if (PC->WasInputKeyJustPressed(EKeys::MouseScrollUp)) ApplyWheel(+1, ES08InputSource::Os);
    if (PC->WasInputKeyJustPressed(EKeys::MouseScrollDown)) ApplyWheel(-1, ES08InputSource::Os);
    if (PC->WasInputKeyJustPressed(EKeys::SpaceBar)) ApplySpace(ES08InputSource::Os);
  }
  // Follow-selection from FollowFromZoom (03 §2: >= 1.2x of the overview; ENV-U9: of the map boards' 2340 uu
  // overview, so their first wheel notch in - the fit, 1872 uu - already follows, as the first notch does on grids).
  FVector FocusTarget = FVector::ZeroVector;
  if (CameraZoom.WantsFollow()) {
    const FString& FocusId = !CommandUi.SelectedFighterId.IsEmpty()
                                 ? CommandUi.SelectedFighterId
                                 : SelectedFighterId;
    for (const FS08BoardFighter& Entry : Fighters) {
      if (Entry.Id == FocusId && Entry.IsAlive()) {
        FocusTarget = BoardModel.CellToWorld(Entry.X, Entry.Y) +
                      FVector(0.0f, 0.0f, 28.0f);
        break;
      }
    }
    // ENV-MAPS: on a topology board CellToWorld is the space's layout point; the follow focus stays on the map
    // extents the overview was fitted to (grids are untouched: their cell centres lie inside W x H x 50 anyway).
    if (BoardModel.bHasTopology) {
      const FVector2D Half = BoardActor ? BoardActor->GetBoardHalfExtentUU() : S08BoardHalfExtentUU(BoardModel);
      FocusTarget.X = FMath::Clamp(FocusTarget.X, -Half.X, Half.X);
      FocusTarget.Y = FMath::Clamp(FocusTarget.Y, -Half.Y, Half.Y);
    }
  }
  CameraZoom.SetFocusTarget(FocusTarget);
  CameraZoom.Tick(DeltaSeconds);
  const float Pitch = FMath::DegreesToRadians(55.0f);
  BoardCamera->SetActorLocationAndRotation(
      CameraZoom.CurrentFocus + FVector(0.0f, CameraZoom.Current * FMath::Cos(Pitch),
                                        CameraZoom.Current * FMath::Sin(Pitch)),
      FRotator(-55.0f, -90.0f, 0.0f));
  if (BoardActor) {
    // Relative to the overview (ENV-U9 included): the world labels keep their K1 size at K1.
    const float Ratio = CameraZoom.Current / CameraZoom.Overview;
    BoardActor->SetFighterLabelZoomRatio(
        Ratio, Ratio < 0.4f &&
                   (!SelectedFighterId.IsEmpty() ||
                    !CommandUi.SelectedFighterId.IsEmpty()));
  }
}

void AS08FlowGameMode::HandleCues(const TArray<FS08Cue>& Cues) {
  // One cue set per authoritative seq (GD-031): the same seq arriving again
  // over the second channel merges silently and never re-fires these.
  bSawCue = true;
  for (const FS08Cue& Cue : Cues) {
    FString Line;
    if (Cue.Type == ES08CueType::FighterMoved) {
      Line = FString::Printf(TEXT("CUE move %s (%d,%d)->(%d,%d) seq=%d"), *Cue.FighterId,
                             Cue.FromX, Cue.FromY, Cue.ToX, Cue.ToY, Cue.SequenceNumber);
    } else {
      Line = FString::Printf(TEXT("CUE damage %s -%d seq=%d"), *Cue.FighterId, Cue.Damage,
                             Cue.SequenceNumber);
      if (BoardActor) {
        BoardActor->ShowDamageNumber(Cue.FighterId, Cue.Damage, Cue.SequenceNumber);
        // Wave 5c-B: HitReact of a v2 figure (a no-op without -ArtPreviewHeroesV2).
        if (Cue.Damage > 0) {
          BoardActor->NotifyFighterAnimEvent(Cue.FighterId, S08HeroesV2::EEvent::Damaged, Cue.SequenceNumber);
        }
        if (BoardActor->IsArtActive() && !bS09ShotDamage &&
            DamageShotAtElapsed < 0.0f && !S09ShotDir.IsEmpty()) {
          DamageShotAtElapsed = Elapsed + 0.2f;
        }
        // W5b-R: the damage number of the first COMBAT (the first damage of a game can be an ability's). The CUE of
        // a combat usually arrives with the snapshot that already closed it (COMBAT-RESULT is traced first, the
        // live combat state is gone): the just-closed combat's target within 2 snapshots counts too. A terminal
        // snapshot (GAME_OVER) is skipped - the result panel owns the screen and the number is not painted.
        const bool bLiveCombatTarget = CommandUi.Combat.bPresent && CommandUi.Combat.TargetFighterId == Cue.FighterId;
        const bool bClosedCombatTarget = LastCombatResult.bValid &&
                                         LastCombatResult.TargetFighterId == Cue.FighterId &&
                                         FMath::Abs(Cue.SequenceNumber - LastCombatResult.SequenceNumber) <= 2;
        const bool bTerminal = Hud.bGameOver ||
                               (Flow.IsValid() && Flow->GetAppliedSnapshot().Phase == TEXT("GAME_OVER"));
        if (BoardActor->IsArtActive() && ArtHud.bTagsEnabled && !bS09ShotDamageCombat &&
            DamageCombatShotAtElapsed < 0.0f && !S09ShotDir.IsEmpty() && !bTerminal &&
            (bLiveCombatTarget || bClosedCombatTarget)) {
          DamageCombatShotAtElapsed = Elapsed + 0.2f;
          DamageCombatShotDeadline = Elapsed + 0.8f;
          FS08Trace::Write(FString::Printf(
              TEXT("S09AUTO damage-combat scheduled fighter=%s amount=%d seq=%d source=%s combatResultSeq=%d"),
              *Cue.FighterId, Cue.Damage, Cue.SequenceNumber,
              bLiveCombatTarget ? TEXT("cue-on-live-combat-target") : TEXT("cue-on-closed-combat-target"),
              LastCombatResult.bValid ? LastCombatResult.SequenceNumber : -1));
        }
      }
    }
    TraceLines.Add(Line);
    FS08Trace::Write(Line);
  }
}

// ---- TASK-022 input ------------------------------------------------------

void AS08FlowGameMode::SelectFighter(const FString& FighterId) {
  const FS08BoardFighter* Fighter = nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == FighterId) Fighter = &Entry;
  }
  if (!Fighter) {
    SelectedFighterId.Reset();
    ReachableCells.Reset();
  } else {
    SelectedFighterId = FighterId;
    ReachableCells = FS08BoardModel::ComputeReachableCells(
        BoardModel, Fighters, FighterId, Fighter->Movement);
  }
  if (BoardActor) BoardActor->SetSelectedFighter(SelectedFighterId, ReachableCells);
  RefreshUi();
}

void AS08FlowGameMode::HandleClick() {
  auto* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor) return;

  // GD-036: no board input after the terminal state.
  if (Hud.bGameOver) return;

  // ART-004 T2.2: every real click is traced (src=os) with its hit result
  // before the unchanged handlers below act on it.
  if (PC->WasInputKeyJustPressed(EKeys::LeftMouseButton)) TraceOsClick(EKeys::LeftMouseButton);
  if (PC->WasInputKeyJustPressed(EKeys::RightMouseButton)) TraceOsClick(EKeys::RightMouseButton);

  if (PC->WasInputKeyJustPressed(EKeys::RightMouseButton)) {
    if (CommandUi.Mode == ES09CommandMode::ManeuverDraft &&
        !CommandUi.SelectedFighterId.IsEmpty()) {
      // Draft stays open; only the drafted-destination focus resets.
      CommandUi.SelectedFighterId.Reset();
      CommandUi.ReachableCells.Reset();
      BoardActor->SetSelectedFighter(FString(), TSet<uint64>());
      Toast = TEXT("draft fighter deselected (draft stays open)");
      ToastUntil = Elapsed + 3.0f;
      RefreshUi();
      return;
    }
    SelectedFighterId.Reset();
    ReachableCells.Reset();
    BoardActor->ClearSelection();
    return;
  }
  if (!PC->WasInputKeyJustPressed(EKeys::LeftMouseButton)) return;

  // ---- GD-033: board clicks draft destinations while a maneuver draft is open
  if (CommandUi.Mode == ES09CommandMode::ManeuverDraft) {
    if (!Flow.IsValid() || Flow->IsManeuverInFlight()) return;
    FHitResult Hit;
    if (!PC->GetHitResultUnderCursor(ECC_Visibility, false, Hit)) return;
    if (AS08FighterActor* FighterActor = Cast<AS08FighterActor>(Hit.GetActor())) {
      const FS08BoardFighter& Fighter = FighterActor->GetFighter();
      if (Flow.IsValid() && Fighter.OwnerId == Flow->GetUserId()) {
        CommandUi.SelectFighter(Fighter.Id, Flow->GetAppliedSnapshot(), BoardModel, Fighters);
        BoardActor->SetSelectedFighter(CommandUi.SelectedFighterId, CommandUi.ReachableCells);
        Toast = FString::Printf(TEXT("draft: selected %s - click a green cell"), *Fighter.Label);
      } else {
        Toast = TEXT("draft: enemy fighters cannot move");
      }
      ToastUntil = Elapsed + 3.0f;
      RefreshUi();
      return;
    }
    int32 CellX, CellY;
    if (!BoardActor->WorldToCell(Hit.ImpactPoint, CellX, CellY)) return;
    if (CommandUi.SelectedFighterId.IsEmpty()) {
      Toast = TEXT("draft: select one of your fighters (blue base) first");
      ToastUntil = Elapsed + 3.0f;
      RefreshUi();
      return;
    }
    FString Reason;
    if (CommandUi.SetDestination(CommandUi.SelectedFighterId, CellX, CellY,
                                 Flow->GetAppliedSnapshot(), BoardModel, Fighters, Reason)) {
      Toast = FString::Printf(TEXT("draft: %s -> (%d,%d) [M/Enter confirm, Esc cancel]"),
                              *CommandUi.SelectedFighterId, CellX, CellY);
    } else {
      Toast = TEXT("draft rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::DiscardDraft) {
    Toast = FString::Printf(TEXT("discard choice open: pick exactly %d cards (1-9 keys)"),
                            CommandUi.PendingDiscard.Count);
    ToastUntil = Elapsed + 3.0f;
    RefreshUi();
    return;
  }
  // ---- GD-034: attack draft clicks pick attacker (own) / target (enemy) ----
  if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
    if (Flow.IsValid() && Flow->IsManeuverInFlight()) return;
    FHitResult Hit;
    if (!PC->GetHitResultUnderCursor(ECC_Visibility, false, Hit)) return;
    if (AS08FighterActor* FighterActor = Cast<AS08FighterActor>(Hit.GetActor())) {
      const FS08BoardFighter& Fighter = FighterActor->GetFighter();
      FString Reason;
      const bool bOwn = Fighter.OwnerId == CommandUi.ViewerId;
      if (bOwn ? CommandUi.SelectAttacker(Fighter.Id, BoardModel, Fighters, Reason)
               : CommandUi.SelectTarget(Fighter.Id, BoardModel, Fighters, Reason)) {
        Toast = FString::Printf(TEXT("attack draft: %s = %s"),
                                bOwn ? TEXT("attacker") : TEXT("target"), *Fighter.Label);
        if (bOwn) {
          // ENV-O6 / GAP-023: the offered target set IS the server's legal
          // set (melee: linked/adjacent; ranged: + shared zone).
          FString Offer;
          for (const FString& TargetId :
               FS09CommandUi::LegalAttackTargets(BoardModel, Fighters, Fighter.Id)) {
            const FS08BoardFighter* Target = FindFighter(TargetId);
            if (!Target) continue;
            const bool bZone = FS09CommandUi::IsZoneOnlyTarget(BoardModel, Fighter, *Target);
            Offer += FString::Printf(TEXT("%s%s@%s(%s)"), Offer.IsEmpty() ? TEXT("") : TEXT(" "),
                                     *TargetId, *BoardModel.CellLabel(Target->X, Target->Y),
                                     bZone ? TEXT("zone") : TEXT("adjacent"));
          }
          FS08Trace::Write(FString::Printf(TEXT("ATTACK draft attacker=%s type=%s at=%s legal=[%s]"),
                                           *Fighter.Id,
                                           FS09CommandUi::IsRangedAttacker(Fighter) ? TEXT("ranged")
                                                                                    : TEXT("melee"),
                                           *BoardModel.CellLabel(Fighter.X, Fighter.Y), *Offer));
          Toast += FString::Printf(TEXT(" - targets: %s"), Offer.IsEmpty() ? TEXT("-") : *Offer);
        }
      } else {
        Toast = TEXT("attack pick rejected: ") + Reason;
      }
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
    }
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::PendingChoice) {
    // GD-035: board clicks drive the pending draft - fighter picks for
    // MOVE/PLACE/TARGET_FIGHTER, cell picks for MOVE/PLACE/CHOOSE_SPACE.
    // Card/option types are hand-strip/panel driven.
    const FString& PendingType = CommandUi.PendingChoice.Type;
    const bool bTakesFighter = PendingType == TEXT("MOVE") ||
                               PendingType == TEXT("PLACE") ||
                               PendingType == TEXT("TARGET_FIGHTER");
    const bool bTakesCell = PendingType == TEXT("MOVE") || PendingType == TEXT("PLACE") ||
                            PendingType == TEXT("CHOOSE_SPACE");
    if (!bTakesFighter && !bTakesCell) {
      Toast = TEXT("pending choice: use the hand (1-9) and the panel keys");
      ToastUntil = Elapsed + 3.0f;
      RefreshUi();
      return;
    }
    FHitResult Hit;
    if (!PC->GetHitResultUnderCursor(ECC_Visibility, false, Hit)) return;
    FString Reason;
    if (AS08FighterActor* FighterActor = Cast<AS08FighterActor>(Hit.GetActor())) {
      if (!bTakesFighter) {
        Toast = TEXT("this choice does not take a fighter");
      } else if (CommandUi.SelectPendingFighter(FighterActor->GetFighter().Id,
                                                 EffectiveSnapshot(), Fighters, Reason)) {
        CommandUi.PendingCells = CommandUi.ComputePendingCells(EffectiveSnapshot(), BoardModel,
                                                               Fighters);
        BoardActor->SetSelectedFighter(CommandUi.PendingFighterId, CommandUi.PendingCells);
        Toast = FString::Printf(TEXT("pending: %s selected - click a green cell or Enter"),
                                *FighterActor->GetFighter().Label);
        if (!bTakesCell) Toast = FString::Printf(TEXT("pending target: %s - Enter confirms"),
                                                 *FighterActor->GetFighter().Label);
      } else {
        Toast = TEXT("pending pick rejected: ") + Reason;
      }
      ToastUntil = Elapsed + 3.0f;
      RefreshUi();
      return;
    }
    int32 CellX, CellY;
    if (!BoardActor->WorldToCell(Hit.ImpactPoint, CellX, CellY)) return;
    if (!bTakesCell) {
      Toast = TEXT("this choice does not take a cell");
      ToastUntil = Elapsed + 3.0f;
      RefreshUi();
      return;
    }
    if (CommandUi.SelectPendingCell(CellX, CellY, EffectiveSnapshot(), BoardModel, Fighters,
                                    Reason)) {
      Toast = FString::Printf(TEXT("pending cell (%d,%d) set - Enter confirms"), CellX, CellY);
    } else {
      Toast = TEXT("pending cell rejected: ") + Reason;
      BoardActor->ShowIllegalCell(CellX, CellY);
      IllegalUntil = Elapsed + 1.5f;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshUi();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::CombatDefense ||
      CommandUi.Mode == ES09CommandMode::CombatResolve) {
    // Combat windows are card-driven: board clicks carry no command.
    Toast = TEXT("combat window: use the hand (1-9) and the panel keys");
    ToastUntil = Elapsed + 3.0f;
    RefreshUi();
    return;
  }

  FString Reason;
  if (Flow.IsValid() && !Flow->CanIssueGameplayCommand(Reason)) {
    Toast = TEXT("input blocked: ") + Reason;
    ToastUntil = Elapsed + 3.0f;
    RefreshUi();
    return;
  }

  FHitResult Hit;
  if (!PC->GetHitResultUnderCursor(ECC_Visibility, false, Hit)) return;
  if (AS08FighterActor* FighterActor = Cast<AS08FighterActor>(Hit.GetActor())) {
    const FS08BoardFighter& Fighter = FighterActor->GetFighter();
    if (Fighter.OwnerId != Flow->GetUserId()) {
      Toast = FString::Printf(TEXT("%s is an ENEMY fighter (red base) - select your own (blue base)"),
                              *Fighter.Label);
      ToastUntil = Elapsed + 3.0f;
    } else {
      SelectFighter(Fighter.Id);
      Toast = FString::Printf(TEXT("selected %s [%s] - green cells are legal destinations"),
                              *Fighter.Label, *Fighter.Id);
      ToastUntil = Elapsed + 3.0f;
    }
    RefreshUi();
    return;
  }
  int32 CellX, CellY;
  if (!BoardActor->WorldToCell(Hit.ImpactPoint, CellX, CellY)) {
    // Original maps: only a space circle is a cell (WorldToCell hit radius).
    Toast = BoardModel.bHasTopology ? TEXT("click outside every space circle - ignored")
                                    : TEXT("click outside the board - ignored");
    ToastUntil = Elapsed + 3.0f;
    RefreshUi();
    return;
  }
  if (SelectedFighterId.IsEmpty()) {
    Toast = TEXT("select one of your fighters (blue base) first");
    ToastUntil = Elapsed + 3.0f;
    RefreshUi();
    return;
  }
  const uint64 Key = FS08BoardModel::CellKey(CellX, CellY);
  if (!ReachableCells.Contains(Key)) {
    // Reason for the illegal destination (TASK-022 P2 requirement).
    const FS08Cell* Cell = BoardModel.CellAt(CellX, CellY);
    const FS08BoardFighter* Mover = nullptr;
    for (const FS08BoardFighter& Entry : Fighters) {
      if (Entry.Id == SelectedFighterId) Mover = &Entry;
    }
    if (Cell && !Cell->IsPassable()) {
      Toast = TEXT("cell is not passable (wall/obstacle/closed door)");
    } else if (FS08BoardModel::FighterAt(Fighters, CellX, CellY, FString())) {
      Toast = TEXT("cell is occupied by another living fighter");
    } else if (Mover) {
      Toast = FString::Printf(
          TEXT("cell (%d,%d) exceeds %s movement %d or an enemy blocks the path"),
          CellX, CellY, *Mover->Label, Mover->Movement);
    } else {
      Toast = TEXT("destination is illegal");
    }
    ToastUntil = Elapsed + 3.0f;
    BoardActor->ShowIllegalCell(CellX, CellY);
    IllegalUntil = Elapsed + 1.5f;
    RefreshUi();
    return;
  }
  TryManeuverTo(CellX, CellY);
}

void AS08FlowGameMode::TryManeuverTo(int32 CellX, int32 CellY) {
  if (!Flow.IsValid()) return;
  const FString PendingId = FS08Contracts::PendingManeuverId(Flow->GetAppliedSnapshot());
  if (PendingId.IsEmpty()) {
    ManeuverTargetX = CellX;       // remembered for the submit leg
    ManeuverTargetY = CellY;
    // P1 regression: a blocked begin (stream not ready/recovery lock) must
    // not leave the await flag armed - the submit leg would never fire.
    bAwaitManeuverFinish = Flow->BeginManeuver();
    if (!bAwaitManeuverFinish) {
      ManeuverTargetX = ManeuverTargetY = -1;
      Toast = TEXT("maneuver blocked - see trace; the state stream is not ready yet");
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
    }
    return;
  }
  FinishPendingManeuver(CellX, CellY);
}

void AS08FlowGameMode::FinishPendingManeuver(int32 CellX, int32 CellY) {
  if (!Flow.IsValid() || SelectedFighterId.IsEmpty()) return;
  const FString PendingId = FS08Contracts::PendingManeuverId(Flow->GetAppliedSnapshot());
  if (PendingId.IsEmpty()) return;
  const FS08BoardFighter* Mover = nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == SelectedFighterId) Mover = &Entry;
  }
  if (!Mover) return;
  TArray<FS08ManeuverMove> Moves;
  FS08ManeuverMove Move;
  Move.FighterId = Mover->Id;
  // Backend path convention (validateManeuver): every entry is one orthogonal
  // step after the previous one, starting from the fighter's current cell -
  // the starting cell itself is NOT part of the path.
  if (!FS08BoardModel::BuildManeuverPath(BoardModel, Fighters, Mover->Id, Mover->Movement,
                                         CellX, CellY, Move.Path) ||
      Move.Path.IsEmpty()) {
    FS08Trace::Write(FString::Printf(TEXT("MANEUVER path to (%d,%d) not buildable"), CellX, CellY));
    return;
  }
  Moves.Add(Move);
  if (!Flow->SubmitManeuver(PendingId, Moves)) {
    bAwaitManeuverFinish = false;
    Toast = TEXT("maneuver not sent - command gate blocked it (see trace)");
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
  }
}

// ---- GD-033 command handlers ---------------------------------------------

void AS08FlowGameMode::HandleHandCardClick(int32 HandIndex) {
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  if (!Own || !Own->Cards.IsValidIndex(HandIndex) || !Flow.IsValid()) return;
  const FS09CardView& Card = Own->Cards[HandIndex];
  if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
    FString Reason;
    if (CommandUi.ToggleAttackCard(Card.InstanceId, EffectiveSnapshot(), Fighters, Reason)) {
      Toast = FString::Printf(TEXT("attack card %s"),
                              CommandUi.AttackCardId == Card.InstanceId ? TEXT("set") : TEXT("cleared"));
    } else {
      Toast = TEXT("attack card rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::CombatDefense) {
    FString Reason;
    if (CommandUi.ToggleDefenseCard(Card.InstanceId, EffectiveSnapshot(), Fighters, Reason)) {
      Toast = FString::Printf(TEXT("defense card %s"),
                              CommandUi.DefenseCardId == Card.InstanceId ? TEXT("set") : TEXT("cleared"));
    } else {
      Toast = TEXT("defense card rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::PendingChoice) {
    FString Reason;
    if (CommandUi.TogglePendingCard(Card.InstanceId, EffectiveSnapshot(), Reason)) {
      Toast = FString::Printf(TEXT("pending pick %s"),
                              CommandUi.PendingCardIds.Contains(Card.InstanceId)
                                  ? TEXT("set") : TEXT("cleared"));
    } else {
      Toast = TEXT("pending pick rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::ManeuverDraft) {
    FString Reason;
    if (CommandUi.ToggleBoostCard(Card.InstanceId, EffectiveSnapshot(), Reason)) {
      Toast = FString::Printf(TEXT("boost %s: %s"),
                              CommandUi.BoostCardId == Card.InstanceId ? TEXT("set") : TEXT("cleared"),
                              *Card.InstanceId);
    } else {
      Toast = TEXT("boost rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::DiscardDraft) {
    FString Reason;
    if (CommandUi.ToggleDiscardCard(Card.InstanceId, EffectiveSnapshot(), Reason)) {
      Toast = FString::Printf(TEXT("discard pick %d/%d"), CommandUi.DiscardSelection.Num(),
                              CommandUi.PendingDiscard.Count);
    } else {
      Toast = TEXT("discard rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::SchemeChoice) {
    // Click (SButton OnClicked) and 1-9 (HandleHudKeys) both land here: the
    // EXACT clicked instance is toggled - dead-banner/non-scheme cards are
    // rejected with a reason instead of falling through to another card.
    FString Reason;
    if (CommandUi.ToggleSchemeCard(Card.InstanceId, EffectiveSnapshot(), Fighters, Reason)) {
      Toast = FString::Printf(TEXT("scheme pick %s - Enter plays THIS card"),
                              CommandUi.SchemeCardId == Card.InstanceId ? TEXT("set") : TEXT("cleared"));
    } else {
      Toast = TEXT("scheme pick rejected: ") + Reason;
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  InspectCard(Card);
  InspectedHandIndex = HandIndex;
  DiscardBrowserIndex = -1; // one selection at a time: drop the pile highlight
  InspectedSource = 0;
  RefreshHud();
}

void AS08FlowGameMode::InspectCard(const FS09CardView& Card) {
  InspectedCard = Card;
  bInspecting = true;
}

void AS08FlowGameMode::HandleDiscardCardClick(int32 PileIndex, int32 CardIndex) {
  const FS09PlayerPanel* Panel =
      PileIndex == 0 ? Hud.ViewerPanel() : Hud.OpponentPanel();
  if (!Panel || !Panel->Discard.IsValidIndex(CardIndex)) return;
  DiscardBrowserPile = PileIndex;
  DiscardBrowserIndex = CardIndex;
  InspectedHandIndex = -1; // one selection at a time: drop the hand highlight
  InspectedSource = PileIndex == 0 ? 1 : 2;
  InspectCard(Panel->Discard[CardIndex]);
  RefreshHud();
}

void AS08FlowGameMode::StepDiscardBrowserSelection(bool bSwitchPile,
                                                   int32 Direction) {
  if (!bDiscardBrowserOpen) return;
  if (bSwitchPile) DiscardBrowserPile = 1 - DiscardBrowserPile;
  const FS09PlayerPanel* Panel =
      DiscardBrowserPile == 0 ? Hud.ViewerPanel() : Hud.OpponentPanel();
  if (!Panel || Panel->Discard.Num() == 0) {
    DiscardBrowserIndex = -1;
    return;
  }
  const int32 Count = Panel->Discard.Num();
  if (DiscardBrowserIndex < 0) {
    DiscardBrowserIndex = Direction >= 0 ? 0 : Count - 1;
  } else {
    DiscardBrowserIndex = (DiscardBrowserIndex + Direction + Count) % Count;
  }
  HandleDiscardCardClick(DiscardBrowserPile, DiscardBrowserIndex);
}

void AS08FlowGameMode::BuildInspectorLines(const FS09CardView& Card,
                                           TArray<FString>& OutLines) {
  if (Card.bHidden) {
    // Placeholder: identity fields were stripped at decode time; this line is
    // the ONLY render path, so a face can never leak through the inspector.
    OutLines.Add(TEXT("hidden card - no face is available to this viewer"));
    return;
  }
  FString Title = FString::Printf(TEXT("%s [%s]"), *Card.Name, *Card.CardType);
  if (!Card.BannerName.IsEmpty()) {
    Title += FString::Printf(TEXT(" (%s)"), *Card.BannerName);
  }
  OutLines.Add(Title);
  OutLines.Add(FString::Printf(TEXT("instance: %s   card: %s"), *Card.InstanceId,
                               Card.CardId.IsEmpty() ? TEXT("-") : *Card.CardId));
  OutLines.Add(FString::Printf(TEXT("attack %d   defense %d   boost %d"),
                               Card.AttackValue, Card.DefenseValue, Card.BoostValue));
  OutLines.Add(Card.NameRu.IsEmpty() ? TEXT("ru: -")
                                     : FString::Printf(TEXT("ru: %s"), *Card.NameRu));
  OutLines.Add(Card.Text.IsEmpty() ? TEXT("text: (none printed)")
                                   : TEXT("text: ") + Card.Text);
}

bool AS08FlowGameMode::TerminalScreenOwnsKeys(ES08Stage Stage, bool bGameOver,
                                              bool bRoomAborted) {
  return Stage == ES08Stage::Started && (bGameOver || bRoomAborted);
}

void AS08FlowGameMode::BeginManeuverCommand() {
  if (!Flow.IsValid()) return;
  FString Reason;
  if (!CommandUi.CanBeginManeuver(Flow->GetAppliedSnapshot(), Reason)) {
    Toast = TEXT("begin maneuver blocked: ") + Reason;
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (Flow->BeginManeuver()) {
    Toast = TEXT("begin maneuver sent (server draws 1 card)");
  } else {
    Toast = TEXT("begin maneuver not sent - command gate blocked it (see trace)");
  }
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

void AS08FlowGameMode::ConfirmDraft() {
  if (!Flow.IsValid()) return;
  if (CommandUi.Mode == ES09CommandMode::ManeuverDraft) {
    FS09ManeuverCommand Command;
    FString Reason;
    if (!CommandUi.ConfirmManeuver(Flow->GetAppliedSnapshot(), BoardModel, Fighters, Command,
                                   Reason)) {
      Toast = TEXT("confirm rejected: ") + Reason;
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
      return;
    }
    FS08Trace::Write(FString::Printf(TEXT("MANEUVER-CONFIRM moves=%d boost=%s"),
                                     Command.Moves.Num(),
                                     Command.BoostCardId.IsEmpty() ? TEXT("none") : TEXT("card")));
    if (S09FirstConfirmSeq < 0) {
      S09FirstConfirmSeq = Flow->GetAppliedSnapshot().SequenceNumber;
    }
    if (Flow->SubmitManeuver(Command.ManeuverId, Command.Moves, Command.BoostCardId)) {
      NextCommandAt = Elapsed + 1.2f;
    } else {
      Toast = TEXT("maneuver confirm not sent - command gate blocked it (see trace)");
    }
    RefreshHud();
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::DiscardDraft) {
    FS09DiscardCommand Command;
    FString Reason;
    if (!CommandUi.ConfirmDiscard(Flow->GetAppliedSnapshot(), Command, Reason)) {
      Toast = TEXT("discard rejected: ") + Reason;
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
      return;
    }
    FS08Trace::Write(FString::Printf(TEXT("DISCARD-CONFIRM pending=%s count=%d ids=%s"),
                                     *Command.PendingId, Command.CardInstanceIds.Num(),
                                     *FString::Join(Command.CardInstanceIds, TEXT(","))));
    if (Flow->DiscardToLimit(Command.PendingId, Command.CardInstanceIds)) {
      NextCommandAt = Elapsed + 1.2f;
    } else {
      Toast = TEXT("discard not sent - command gate blocked it (see trace)");
    }
    RefreshHud();
    return;
  }
}

void AS08FlowGameMode::CancelDraft() {
  if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
    // Local-only close; nothing was sent to the server.
    CommandUi.Mode = ES09CommandMode::None;
    CommandUi.AttackAttackerId.Reset();
    CommandUi.AttackTargetId.Reset();
    CommandUi.AttackCardId.Reset();
    Toast = TEXT("attack draft closed (nothing was sent)");
    ToastUntil = Elapsed + 3.0f;
    FS08Trace::Write(TEXT("ATTACK-DRAFT-CANCEL local"));
    RefreshHud();
    return;
  }
  if (CommandUi.Mode != ES09CommandMode::ManeuverDraft) return;
  CommandUi.CancelDraft();
  if (BoardActor) BoardActor->SetSelectedFighter(FString(), TSet<uint64>());
  Toast = TEXT("draft cleared locally - the server draw stays committed; re-click cells to resume");
  ToastUntil = Elapsed + 4.0f;
  FS08Trace::Write(TEXT("DRAFT-CANCEL local (pending stays, no second begin)"));
  RefreshHud();
}

void AS08FlowGameMode::EndTurnCommand() {
  if (!Flow.IsValid()) return;
  const FS08Snapshot& Snap = Flow->GetAppliedSnapshot();
  if (CommandUi.Mode == ES09CommandMode::ManeuverDraft ||
      CommandUi.Mode == ES09CommandMode::DiscardDraft) {
    Toast = TEXT("finish the open draft first");
  } else if (!Hud.bViewerTurn) {
    Toast = TEXT("not your turn");
  } else if (Hud.ActionsRemaining > 0) {
    Toast = FString::Printf(TEXT("%d action(s) remaining - maneuver first"), Hud.ActionsRemaining);
  } else if (!FS08Contracts::PendingManeuverId(Snap).IsEmpty()) {
    Toast = TEXT("a pending maneuver is open - confirm it first");
  } else if (CommandUi.bHasPendingChoice) {
    // Server: 'Resolve the pending choice first' - no endTurn roundtrip.
    Toast = TEXT("resolve the pending choice first");
  } else if (!FS08FlowController::IsEndTurnPhase(Snap.Phase)) {
    // Server network guard (game-turn.guard) only accepts endTurn in
    // ACTION_MANEUVER/ACTION_ATTACK: a send from COMBAT/COMBAT_RESOLVE burns
    // an authoritative 'Invalid phase' rejection (8 in the S09 11:47 run).
    Toast = FString::Printf(TEXT("end turn waits for an action phase (now %s)"),
                            *Snap.Phase);
  } else if (Flow->EndTurn()) {
    FS08Trace::Write(TEXT("ENDTURN sent"));
    Toast = TEXT("end turn sent");
  } else {
    Toast = TEXT("end turn not sent - command gate blocked it (see trace)");
  }
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

// ---- GD-034 combat commands -------------------------------------------------

void AS08FlowGameMode::BeginAttackDraft() {
  if (!Flow.IsValid()) return;
  FString Reason;
  if (!CommandUi.CanOpenAttackDraft(EffectiveSnapshot(), Reason)) {
    Toast = TEXT("attack draft blocked: ") + Reason;
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  CommandUi.Mode = ES09CommandMode::AttackDraft;
  CommandUi.AttackAttackerId.Reset();
  CommandUi.AttackTargetId.Reset();
  CommandUi.AttackCardId.Reset();
  Toast = TEXT("attack draft open: click an own fighter with an enemy in range, pick a card (1-9)");
  ToastUntil = Elapsed + 4.0f;
  RefreshHud();
}

void AS08FlowGameMode::NoDefenseCommand() {
  if (!Flow.IsValid()) return;
  if (CommandUi.Mode != ES09CommandMode::CombatDefense) {
    Toast = TEXT("'no defense' is only legal while the defense window is yours");
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  const FS08CombatInfo& Combat = CommandUi.Combat;
  if (Combat.bHasTimeoutAt && Combat.SecondsUntilDeadline() <= 0.0) {
    Toast = TEXT("the defense window has expired (server deadline)");
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (Flow->ResolveCombat()) {
    FS08Trace::Write(TEXT("NO-DEFENSE sent (defender closes the window)"));
    Toast = TEXT("no defense - resolving");
  } else {
    Toast = TEXT("no defense not sent - command gate blocked it (see trace)");
  }
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

void AS08FlowGameMode::ResolveCombatCommand() {
  if (!Flow.IsValid()) return;
  FString Reason;
  if (!CommandUi.CanResolveCombat(EffectiveSnapshot(), Reason)) {
    Toast = TEXT("resolve blocked: ") + Reason;
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (Flow->ResolveCombat()) {
    FS08Trace::Write(TEXT("RESOLVE sent"));
    Toast = TEXT("resolve sent");
  } else {
    Toast = TEXT("resolve not sent - command gate blocked it (see trace)");
  }
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

void AS08FlowGameMode::DeclinePendingChoiceCommand() {
  if (!Flow.IsValid()) return;
  if (CommandUi.Mode != ES09CommandMode::PendingChoice) {
    Toast = TEXT("no optional choice to decline");
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  FS09PendingChoiceCommand Command;
  FString Reason;
  if (!CommandUi.ConfirmPendingChoice(EffectiveSnapshot(), true, Command, Reason)) {
    // Toast is UI-only: without this line a rejected auto-decline is invisible
    // in the published trace (the S09 demo gate then fails on a missing
    // PEND-DECLINE line with no diagnostic).
    FS08Trace::Write(TEXT("PEND-DECLINE rejected: ") + Reason);
    Toast = TEXT("decline rejected: ") + Reason;
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  if (Flow->DeclinePendingEffect(Command.EffectId)) {
    FS08Trace::Write(FString::Printf(TEXT("PEND-DECLINE sent type=%s"),
                                     *CommandUi.PendingChoice.Type));
    Toast = TEXT("boost declined");
  } else {
    Toast = TEXT("decline not sent - command gate blocked it (see trace)");
  }
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

void AS08FlowGameMode::PlaySchemeCommand() {
  if (!Flow.IsValid()) return;
  // G toggles: an open picker closes WITHOUT sending anything (the manual
  // command NEVER auto-sends a card - the pre-fix behavior spent the first
  // playable scheme, i.e. the WRONG card when two were legal).
  if (CommandUi.Mode == ES09CommandMode::SchemeChoice) {
    CommandUi.CancelSchemeChoice();
    FS08Trace::Write(TEXT("SCHEME-DRAFT cancelled (G/Esc)"));
    Toast = TEXT("scheme choice cancelled");
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  const FS08Snapshot& Snap = EffectiveSnapshot();
  FString Reason;
  if (!CommandUi.CanOpenSchemeChoice(Snap, Reason)) {
    Toast = Reason;
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  const int32 Playable = CommandUi.CountPlayableSchemes(Snap, Fighters);
  if (Playable <= 0) {
    Toast = TEXT("no playable scheme card in hand");
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return;
  }
  CommandUi.OpenSchemeChoice();
  FS08Trace::Write(FString::Printf(TEXT("SCHEME-DRAFT open (playable schemes: %d)"), Playable));
  Toast = TEXT("scheme choice: click or 1-9 picks the EXACT card; Enter plays it; G/Esc cancels");
  ToastUntil = Elapsed + 4.0f;
  RefreshHud();
}

void AS08FlowGameMode::ConfirmSchemeCommand() {
  if (!Flow.IsValid()) return;
  const FS08Snapshot& Snap = EffectiveSnapshot();
  FString InstanceId;
  FString Reason;
  if (!CommandUi.ConfirmScheme(Snap, Fighters, InstanceId, Reason)) {
    // Stale/dead selection: report, clear the pick, KEEP the picker open so
    // the next pick is another explicit choice. A different card is NEVER
    // auto-sent (the review's wrong-card spend bug).
    CommandUi.SchemeCardId.Reset();
    FS08Trace::Write(TEXT("SCHEME-DRAFT rejected: ") + Reason);
    Toast = TEXT("scheme rejected: ") + Reason;
    ToastUntil = Elapsed + 4.0f;
    RefreshHud();
    return;
  }
  if (Flow->PlayScheme(InstanceId)) {
    FS08Trace::Write(TEXT("SCHEME sent"));
    CommandUi.Mode = ES09CommandMode::None;
    CommandUi.SchemeCardId.Reset();
    Toast = TEXT("scheme sent");
  } else {
    // Keep the picker open with the pick intact: the command was NOT sent, so
    // closing would silently eat the player's choice.
    Toast = TEXT("scheme not sent - command gate blocked it (see trace)");
  }
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

bool AS08FlowGameMode::ConfirmCombat() {
  if (!Flow.IsValid()) return false;
  const FS08Snapshot& Snap = EffectiveSnapshot();
  FString Reason;
  if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
    FS09AttackCommand Command;
    if (!CommandUi.ConfirmAttack(Snap, BoardModel, Fighters, Command, Reason)) {
      Toast = TEXT("attack rejected: ") + Reason;
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
      return false;
    }
    // P1 regression (packaged run 2026-09-27): "ATTACK sent" must mean the
    // controller actually dispatched it - a gate-blocked attack used to log
    // "sent", flip the mode and stall the seat forever at seq1.
    const bool bSent = Flow->Attack(Command.AttackerFighterId, Command.CardInstanceId,
                                    Command.TargetFighterId);
    if (bSent) {
      FS08Trace::Write(TEXT("ATTACK sent"));
      Toast = TEXT("attack sent");
    } else {
      Toast = TEXT("attack not sent - command gate blocked it (see trace)");
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return bSent;
  }
  if (CommandUi.Mode == ES09CommandMode::CombatDefense) {
    FS09DefenseCommand Command;
    if (!CommandUi.ConfirmDefense(Snap, Fighters, Command, Reason)) {
      Toast = TEXT("defense rejected: ") + Reason;
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
      return false;
    }
    const bool bSent = Flow->PlayDefense(Command.CardInstanceId);
    if (bSent) {
      FS08Trace::Write(TEXT("DEFENSE sent"));
      Toast = TEXT("defense sent");
    } else {
      Toast = TEXT("defense not sent - command gate blocked it (see trace)");
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return bSent;
  }
  if (CommandUi.Mode == ES09CommandMode::PendingChoice) {
    FS09PendingChoiceCommand Command;
    if (!CommandUi.ConfirmPendingChoice(Snap, false, Command, Reason)) {
      Toast = TEXT("choice rejected: ") + Reason;
      ToastUntil = Elapsed + 3.0f;
      RefreshHud();
      return false;
    }
    const bool bSent = Flow->ResolvePendingEffect(
        Command.EffectId, Command.FighterId, Command.bHasCell, Command.CellX, Command.CellY,
        Command.OptionIndex >= 0, Command.OptionIndex, Command.CardIds);
    if (bSent) {
      FS08Trace::Write(FString::Printf(TEXT("PEND-RESOLVE sent type=%s stage=%d id=%s"),
                                       *CommandUi.PendingChoice.Type,
                                       CommandUi.PendingChoice.Stage, *Command.EffectId));
      Toast = TEXT("choice sent");
    } else {
      Toast = TEXT("choice not sent - command gate blocked it (see trace)");
    }
    ToastUntil = Elapsed + 3.0f;
    RefreshHud();
    return bSent;
  }
  if (CommandUi.Mode == ES09CommandMode::CombatResolve) {
    ResolveCombatCommand();
  }
  if (CommandUi.Mode == ES09CommandMode::SchemeChoice) {
    ConfirmSchemeCommand();
  }
  return false;
}

void AS08FlowGameMode::HandleHudKeys() {
  auto* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !Flow.IsValid() ||
      (!bS09Probe && Flow->GetStage() != ES08Stage::Started)) {
    return;
  }

  if (PC->WasInputKeyJustPressed(EKeys::F10)) {
    // Operator-only debug overlay (login/lobby/trace panel) during gameplay.
    bDebugPanelForced = !bDebugPanelForced;
    RefreshUi();
    return;
  }

  // GD-036 + S10/GD-040: a terminal screen owns the keyboard - the result
  // panel (GAME_OVER) AND the interrupted-room panel (authoritative ABORTED
  // row): every gameplay binding is dead there; L/Enter is the only live
  // action (lobby return), exactly as both panels promise.
  if (!bS09Probe && TerminalScreenOwnsKeys(Flow->GetStage(), Hud.bGameOver,
                                           Flow->IsRoomAborted())) {
    if (PC->WasInputKeyJustPressed(EKeys::L) ||
        PC->WasInputKeyJustPressed(EKeys::Enter)) {
      ReturnToLobbyCommand();
    }
    return;
  }

  if (PC->WasInputKeyJustPressed(EKeys::M)) {
    BeginManeuverCommand();
  } else if (PC->WasInputKeyJustPressed(EKeys::E)) {
    EndTurnCommand();
  } else if (PC->WasInputKeyJustPressed(EKeys::A)) {
    if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
      CancelDraft(); // A toggles the draft closed
    } else {
      BeginAttackDraft();
    }
  } else if (PC->WasInputKeyJustPressed(EKeys::N)) {
    NoDefenseCommand();
  } else if (PC->WasInputKeyJustPressed(EKeys::R)) {
    ResolveCombatCommand();
  } else if (PC->WasInputKeyJustPressed(EKeys::G)) {
    PlaySchemeCommand();
  } else if (PC->WasInputKeyJustPressed(EKeys::X)) {
    DeclinePendingChoiceCommand();
  } else if (PC->WasInputKeyJustPressed(EKeys::D)) {
    // GD-032: public discard browser toggle (read-only browsing - safe while
    // any draft is open; the panels box is separate from the command panel).
    bDiscardBrowserOpen = !bDiscardBrowserOpen;
    DiscardBrowserIndex = -1;
    RefreshHud();
  } else if (bDiscardBrowserOpen &&
             (PC->WasInputKeyJustPressed(EKeys::Left) ||
              PC->WasInputKeyJustPressed(EKeys::Right) ||
              PC->WasInputKeyJustPressed(EKeys::Up) ||
              PC->WasInputKeyJustPressed(EKeys::Down))) {
    StepDiscardBrowserSelection(
        PC->WasInputKeyJustPressed(EKeys::Up) ||
            PC->WasInputKeyJustPressed(EKeys::Down),
        PC->WasInputKeyJustPressed(EKeys::Left)
            ? -1
            : (PC->WasInputKeyJustPressed(EKeys::Right) ? 1 : 0));
  } else if (PC->WasInputKeyJustPressed(EKeys::Enter)) {
    if (CommandUi.Mode == ES09CommandMode::ManeuverDraft ||
        CommandUi.Mode == ES09CommandMode::DiscardDraft) {
      ConfirmDraft();
    } else if (CommandUi.Mode != ES09CommandMode::None) {
      ConfirmCombat();
    }
  } else if (PC->WasInputKeyJustPressed(EKeys::Escape)) {
    if (CommandUi.Mode == ES09CommandMode::ManeuverDraft ||
        CommandUi.Mode == ES09CommandMode::AttackDraft) {
      CancelDraft();
    } else if (CommandUi.Mode == ES09CommandMode::SchemeChoice) {
      CommandUi.CancelSchemeChoice();
      FS08Trace::Write(TEXT("SCHEME-DRAFT cancelled (G/Esc)"));
      RefreshHud();
    } else if (bDiscardBrowserOpen) {
      // Read-only overlay closes before the broader selection clear.
      bDiscardBrowserOpen = false;
      DiscardBrowserIndex = -1;
      RefreshHud();
    } else {
      SelectedFighterId.Reset();
      ReachableCells.Reset();
      bInspecting = false;
      InspectedHandIndex = -1;
      if (BoardActor) BoardActor->ClearSelection();
      RefreshHud();
    }
  } else if (PC->WasInputKeyJustPressed(EKeys::I)) {
    bInspecting = !bInspecting;
    RefreshHud();
  } else {
    static const FKey NumberKeys[9] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four,
                                       EKeys::Five, EKeys::Six, EKeys::Seven, EKeys::Eight,
                                       EKeys::Nine};
    for (int32 I = 0; I < 9; ++I) {
      if (PC->WasInputKeyJustPressed(NumberKeys[I])) {
        if (bS09Probe) {
          // Route split: attribute the handler run to whichever key source is
          // armed (1 = real Slate event, 2 = direct InputKey fallback).
          if (S09KeyRouteArmed == 1) {
            ++S09SlateKeySeen;
          } else if (S09KeyRouteArmed == 2) {
            ++S09DirectKeySeen;
          }
          ++S09KeyProbeSeen;
        }
        if (CommandUi.Mode == ES09CommandMode::PendingChoice &&
            CommandUi.PendingChoice.Type == TEXT("CHOOSE_ONE")) {
          // GD-035: number keys pick labeled options, not hand cards.
          FString Reason;
          if (CommandUi.SelectPendingOption(I, Reason)) {
            Toast = TEXT("option selected - Enter confirms");
          } else {
            Toast = TEXT("option rejected: ") + Reason;
          }
          ToastUntil = Elapsed + 3.0f;
          RefreshHud();
        } else {
          HandleHandCardClick(I);
        }
        break;
      }
    }
  }
}

// ---- GD-033 auto drive -----------------------------------------------------

namespace {
// One step for FighterId into a reachable board neighbour (a linked space on
// an original map, the orthogonal cells +X/-X/+Y/-Y on a grid); returns
// false when no neighbour is legal (blocked board edge case).
bool StepOneCell(FS09CommandUi& Ui, const FS08Snapshot& Snap, const FS08BoardModel& Board,
                 const TArray<FS08BoardFighter>& Fighters, const FString& FighterId) {
  Ui.SelectFighter(FighterId, Snap, Board, Fighters);
  const FS08BoardFighter* Fighter = nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == FighterId) Fighter = &Entry;
  }
  if (!Fighter) return false;
  FString Reason;
  for (const FIntPoint& Next : Board.Neighbours(FIntPoint(Fighter->X, Fighter->Y))) {
    if (Ui.SetDestination(FighterId, Next.X, Next.Y, Snap, Board, Fighters, Reason)) {
      return true;
    }
  }
  return false;
}
} // namespace

void AS08FlowGameMode::ReturnToLobbyCommand() {
  if (!Flow.IsValid()) return;
  if (bS09LobbyReturnSent) {
    Toast = TEXT("lobby return already sent");
    ToastUntil = Elapsed + 3.0f;
    return;
  }
  bS09LobbyReturnSent = true;
  // leaveGame on a FINISHED row no longer aborts (saveState marks the Game
  // FINISHED at GAME_OVER); the local stage flips to Lobby on the reply.
  FS08Trace::Write(TEXT("RESULT lobby-return sent (leaveGame)"));
  Flow->LeaveRoom();
  Toast = TEXT("returning to the lobby");
  ToastUntil = Elapsed + 3.0f;
  RefreshHud();
}

void AS08FlowGameMode::DriveS09ResultFlow() {
  // Bounded result-screen capture, one leaveGame, bounded lobby shot, then an
  // EARLY exit - the 10:37 run idled ~300s at a terminal state; once the
  // result/lobby evidence is complete there is nothing left to wait for.
  if (!bS09ShotResultScreen) {
    if (S09ShotDir.IsEmpty()) {
      // No evidence dir: skip straight to the lobby return.
      bS09ShotResultScreen = true;
      S09ShotResultScreenPath.Reset();
    } else {
      // UI settle (the 11:47 lesson): the shot fired on the SAME tick the
      // result panel was built and caught Slate mid-paint - header/outcome
      // present, supporting text and button absent. Wait a bounded beat
      // (dozens of painted frames at the demo's 30 FPS cap) first.
      if (ResultPanelBuiltAtElapsed < 0.0f) ResultPanelBuiltAtElapsed = Elapsed;
      if (Elapsed < ResultPanelBuiltAtElapsed + 2.0f) return;
      bS09ShotResultScreen = true;
      S09ShotResultScreenPath = S09ShotDir / TEXT("s09-result-screen.png");
      ShotResultScreenAtElapsed = Elapsed;
      FS08Trace::Write(TEXT("S09AUTO result-screen shot"));
      TakeEvidenceShot(S09ShotResultScreenPath);
      return;
    }
  }
  if (!S09ShotResultScreenPath.IsEmpty() &&
      !FPaths::FileExists(S09ShotResultScreenPath)) {
    if (ShotResultScreenAtElapsed < 0.0f) ShotResultScreenAtElapsed = Elapsed;
    if (Elapsed < ShotResultScreenAtElapsed + 12.0f) return;
    FS08Trace::Write(TEXT("S09AUTO result shot file never appeared - proceeding WITHOUT the shot"));
    S09ShotResultScreenPath.Reset();
  }
  if (!bS09LobbyReturnSent) {
    // A failed leave must not be fired again on every auto-drive tick. The
    // result screen remains interactive so L/the button can retry explicitly.
    if (bS09AutoLeaveRetryBlocked) return;
    ReturnToLobbyCommand();
    return;
  }
  if (Flow->GetStage() != ES08Stage::Lobby) {
    // leaveGame reply drives the stage; WS/HTTP may still deliver the last
    // GAME_OVER body first. Bounded by the driver's own run timeout.
    return;
  }
  // The gameplay HUD is already cleared: the Lobby stage transition fired
  // OnStageChanged -> ClearGameplayHud (manual and auto paths share it).
  if (!bS09ShotLobby) {
    if (S09ShotDir.IsEmpty()) {
      bS09ShotLobby = true;
    } else {
      // Capture only after the 'returning to the lobby' toast CLEARED and
      // Slate settled: the shot must show the clean lobby panel, not the
      // transition overlay.
      const float NotBefore = FMath::Max(Elapsed + 2.0f, ToastUntil + 1.0f);
      if (LobbyShotNotBeforeElapsed < 0.0f) LobbyShotNotBeforeElapsed = NotBefore;
      if (Elapsed < LobbyShotNotBeforeElapsed) return;
      bS09ShotLobby = true;
      S09ShotLobbyPath = S09ShotDir / TEXT("s09-lobby-return.png");
      ShotLobbyAtElapsed = Elapsed;
      FS08Trace::Write(TEXT("S09AUTO lobby-return shot"));
      TakeEvidenceShot(S09ShotLobbyPath);
      return;
    }
  }
  if (!S09ShotLobbyPath.IsEmpty() && !FPaths::FileExists(S09ShotLobbyPath)) {
    if (ShotLobbyAtElapsed < 0.0f) ShotLobbyAtElapsed = Elapsed;
    if (Elapsed < ShotLobbyAtElapsed + 12.0f) return;
    FS08Trace::Write(TEXT("S09AUTO lobby shot file never appeared - proceeding WITHOUT the shot"));
    S09ShotLobbyPath.Reset();
  }
  if (bS09DuelComplete) return;
  bS09DuelComplete = true;
  FS08Trace::Write(TEXT("S09AUTO duel flow complete (GAME_OVER -> result shown -> lobby return) - exiting"));
  // Early exit with every evidence gate closed; only the -S09Flow driver
  // reaches this (automation/editor runs never pass -S09Flow).
  FPlatformMisc::RequestExit(false);
}

// ---- S10/GD-040 packaged ABORTED proof (opt-in -S10AbortProof) -------------

void AS08FlowGameMode::RunS10AbortProof() {
  // Dormant without the explicit CLI opt-in: the normal UI path (manual
  // L/Enter on the interruption screen) is untouched.
  if (!bS10AbortProof || !Flow.IsValid()) return;
  using EStep = FS10AbortProofTransitions::EStep;
  const ES08Stage Stage = Flow->GetStage();
  // Live = the authoritative ABORTED room row on the live match; tail = the
  // Lobby reached by THIS drive's own leave (a manual leave never arms it).
  const bool bAbortedLive = Stage == ES08Stage::Started && Flow->IsRoomAborted();
  const bool bInLobby = Stage == ES08Stage::Lobby && bS10AbortLeaveSent;

  switch (S10AbortProofStep) {
    case EStep::Idle:
      if (!bAbortedLive) return; // dormant until the interruption row lands
      S10AbortPanelBuiltAtElapsed = Elapsed;
      S10AbortProofStep = FS10AbortProofTransitions::Advance(
          S10AbortProofStep, /*bAbortProofEnabled=*/true, bAbortedLive, bInLobby, false);
      FS08Trace::Write(TEXT(
          "S10ABORTPROOF authoritative ABORTED row - interruption screen (no victory/defeat is declared)"));
      return;
    case EStep::ScreenShotWait: {
      if (S09ShotDir.IsEmpty()) {
        // No evidence dir: skip the capture, still leave exactly once.
        S10AbortProofStep = FS10AbortProofTransitions::Advance(
            S10AbortProofStep, true, bAbortedLive, bInLobby, /*bEvidenceSettled=*/true);
        return;
      }
      if (!bS10AbortScreenShotTaken) {
        // Let the interruption panel paint many frames first (the 11:47
        // mid-paint lesson from the result screen).
        if (S10AbortPanelBuiltAtElapsed < 0.0f) S10AbortPanelBuiltAtElapsed = Elapsed;
        if (Elapsed < S10AbortPanelBuiltAtElapsed + 2.0f) return;
        bS10AbortScreenShotTaken = true;
        S10AbortScreenShotPath = S09ShotDir / TEXT("s10-aborted-screen.png");
        S10AbortScreenShotAtElapsed = Elapsed;
        FS08Trace::Write(TEXT("S10ABORTPROOF aborted-screen shot (interruption panel painted)"));
        TakeEvidenceShot(S10AbortScreenShotPath);
        return;
      }
      bool bSettled = true;
      if (!S10AbortScreenShotPath.IsEmpty() &&
          !FPaths::FileExists(S10AbortScreenShotPath)) {
        if (S10AbortScreenShotAtElapsed < 0.0f) S10AbortScreenShotAtElapsed = Elapsed;
        bSettled = Elapsed >= S10AbortScreenShotAtElapsed + 12.0f;
        if (bSettled) {
          FS08Trace::Write(TEXT(
              "S10ABORTPROOF screen shot file never appeared - proceeding WITHOUT the shot"));
          S10AbortScreenShotPath.Reset();
        }
      }
      if (bSettled) {
        S10AbortProofStep = FS10AbortProofTransitions::Advance(
            S10AbortProofStep, true, bAbortedLive, bInLobby, /*bEvidenceSettled=*/true);
      }
      return;
    }
    case EStep::LeaveOnce:
      if (!bS10AbortLeaveSent) {
        if (!bAbortedLive) return; // manual interference left Started - stay put
        bS10AbortLeaveSent = true;
        bS09LobbyReturnSent = true; // share the one-send guard + OnLeaveFailed
        FS08Trace::Write(TEXT(
            "S10ABORTPROOF leave sent (one leaveGame - the ONLY command after the abort)"));
        Flow->LeaveRoom();
        return;
      }
      // A failed auto leave needs an explicit manual retry - never a second
      // auto send (the shared guard blocked it; OnLeaveFailed traced the loss).
      if (bS09AutoLeaveRetryBlocked) {
        if (!bS10AbortProofComplete) {
          bS10AbortProofComplete = true;
          FS08Trace::Write(TEXT(
              "S10ABORTPROOF leave FAILED - manual retry required; ending without the lobby proof"));
          FPlatformMisc::RequestExit(false);
        }
        return;
      }
      if (!bInLobby) return; // leaveGame reply drives the stage to Lobby
      S10AbortLobbyNotBeforeElapsed = FMath::Max(Elapsed + 2.0f, ToastUntil + 1.0f);
      S10AbortProofStep = FS10AbortProofTransitions::Advance(
          S10AbortProofStep, true, bAbortedLive, bInLobby, false);
      return;
    case EStep::LobbyShotWait: {
      if (S09ShotDir.IsEmpty()) {
        S10AbortProofStep = FS10AbortProofTransitions::Advance(
            S10AbortProofStep, true, bAbortedLive, bInLobby, /*bEvidenceSettled=*/true);
        break; // straight to the clean exit
      }
      if (!bS10AbortLobbyShotTaken) {
        // Capture only after the 'returning to the lobby' toast CLEARED and
        // Slate settled - the shot must show the clean lobby panel, not the
        // transition overlay (same gate as the S09 lobby shot).
        if (S10AbortLobbyNotBeforeElapsed < 0.0f) {
          S10AbortLobbyNotBeforeElapsed = FMath::Max(Elapsed + 2.0f, ToastUntil + 1.0f);
        }
        if (Elapsed < S10AbortLobbyNotBeforeElapsed) return;
        bS10AbortLobbyShotTaken = true;
        S10AbortLobbyShotPath = S09ShotDir / TEXT("s10-aborted-lobby.png");
        S10AbortLobbyShotAtElapsed = Elapsed;
        FS08Trace::Write(TEXT(
            "S10ABORTPROOF aborted-lobby shot (board torn down by the stage transition)"));
        TakeEvidenceShot(S10AbortLobbyShotPath);
        return;
      }
      bool bSettled = true;
      if (!S10AbortLobbyShotPath.IsEmpty() &&
          !FPaths::FileExists(S10AbortLobbyShotPath)) {
        if (S10AbortLobbyShotAtElapsed < 0.0f) S10AbortLobbyShotAtElapsed = Elapsed;
        bSettled = Elapsed >= S10AbortLobbyShotAtElapsed + 12.0f;
        if (bSettled) {
          FS08Trace::Write(TEXT(
              "S10ABORTPROOF lobby shot file never appeared - proceeding WITHOUT the shot"));
          S10AbortLobbyShotPath.Reset();
        }
      }
      if (bSettled) {
        S10AbortProofStep = FS10AbortProofTransitions::Advance(
            S10AbortProofStep, true, bAbortedLive, bInLobby, /*bEvidenceSettled=*/true);
      } else {
        return;
      }
      break;
    }
    case EStep::Complete:
      return;
  }
  // Lobby evidence settled: exit cleanly once (nothing left to wait for).
  if (S10AbortProofStep == EStep::Complete && !bS10AbortProofComplete) {
    bS10AbortProofComplete = true;
    FS08Trace::Write(TEXT(
        "S10ABORTPROOF complete (ABORTED screen -> one leaveGame -> clean lobby) - exiting"));
    FPlatformMisc::RequestExit(false);
  }
}

void AS08FlowGameMode::RunS09Auto() {
  if (!bAutoS09 || !Flow.IsValid()) return;
  // S10/GD-040 opt-in: the -S10AbortProof drive owns the WHOLE post-abort
  // tail. Without this carve-out the S09 result tail would fire from the
  // Lobby (the abort leave sets bS09LobbyReturnSent via the shared guard) and
  // shoot/exit its GAME_OVER flow over an interrupted match - an abort must
  // never drive the result path.
  if (bS10AbortProof && (Flow->IsRoomAborted() || bS10AbortLeaveSent)) return;
  // GD-036: the result tail must keep ticking AFTER the lobby return - the
  // leaveGame reply flips the stage to Lobby, and without this carve-out the
  // driver dies at its first stage gate with the lobby shot never taken and
  // the early exit never firing (the client then idles to -S08ExitAfter).
  const ES08Stage S09AutoStage = Flow->GetStage();
  const bool bTerminalTail = S09AutoStage == ES08Stage::Lobby && bS09LobbyReturnSent;
  if (S09AutoStage != ES08Stage::Started && !bTerminalTail) return;
  // S10/GD-040: the interrupted-room screen holds no gameplay for the driver
  // - every command gate rejects with the interruption reason, and the
  // per-tick decision tail flooded the log with repeated "blocked" traces in
  // the live ABORTED run. Leave (the only live action) is never a blind
  // gameplay send.
  if (S09AutoStage == ES08Stage::Started && Flow->IsRoomAborted()) return;
  if (Flow->IsManeuverInFlight()) return;
  if (Elapsed < NextCommandAt) return;
  // Hold every follow-up command until the requested combat-result shot hit
  // the disk (bounded): the frame is captured a few ticks after the request,
  // and the next draft would repaint the command panel into that frame.
  if (bS09ShotResult && !S09ShotResultPath.IsEmpty() &&
      !FPaths::FileExists(S09ShotResultPath)) {
    if (ShotResultAtElapsed < 0.0f || Elapsed < ShotResultAtElapsed + 12.0f) return;
    FS08Trace::Write(TEXT("S09AUTO result shot file never appeared - proceeding WITHOUT the shot"));
    S09ShotResultPath.Reset();
  }
  const FS08Snapshot& Snap = Flow->GetAppliedSnapshot();
  // Accepted leave clears the old applied snapshot before the lobby shot.
  // Keep driving the terminal tail from the explicit Lobby/leave marker.
  if (bTerminalTail || Snap.Phase == TEXT("GAME_OVER")) {
    DriveS09ResultFlow(); // GD-036: result evidence + lobby return + early exit
    return;
  }
  if (static_cast<int32>(CommandUi.Mode) != LastAutoMode) {
    LastAutoMode = static_cast<int32>(CommandUi.Mode);
    FS08Trace::Write(FString::Printf(
        TEXT("S09AUTO drive mode=%d plan=[%s] phase=%s turn=%s"),
        static_cast<int32>(CommandUi.Mode), *FString::Join(S09CombatPlan, TEXT("+")),
        *Snap.Phase, *Snap.CurrentTurnPlayerId));
  }

  // Own-turn boundary: a turn count we have not seen while it is our move.
  if (Hud.bViewerTurn && Snap.TurnCount != LastSeenTurnCount) {
    LastSeenTurnCount = Snap.TurnCount;
    ++OwnTurnIndex;
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO own turn #%d (turnCount=%d)"), OwnTurnIndex,
                                     Snap.TurnCount));
  }

  // ---- GD-034 combat auto-drive (plan tokens from -S09Combat=) ----
  auto HasPlan = [this](const TCHAR* Token) {
    for (const FString& Entry : S09CombatPlan) {
      if (Entry == Token) return true;
    }
    return false;
  };
  // Episode boundary for the bounded pending retries: leaving PendingChoice
  // means the head CLOSED (authoritative resolve/decline). A re-opened head
  // may REUSE the same stable id (the Medusa ability re-arms on every attack)
  // - without this reset three SUCCESSFUL cycles of one id tripped the
  // "stayed open" hold and actually stranded the fresh head (S09 10:29 run).
  if (CommandUi.Mode != ES09CommandMode::PendingChoice) {
    S09PendingAutoBudget.Observe(FString());
  }
  if (CommandUi.Mode == ES09CommandMode::CombatDefense) {
    // Bounded UI-capture wait (GD-034): hold for the file up to 12s after the
    // request, then proceed WITHOUT it and say so - never wait forever.
    if (!S09ShotDefensePath.IsEmpty() && !FPaths::FileExists(S09ShotDefensePath)) {
      if (ShotDefenseAtElapsed < 0.0f || Elapsed < ShotDefenseAtElapsed + 12.0f) return;
      FS08Trace::Write(TEXT("S09AUTO defense shot file never appeared - proceeding WITHOUT the shot"));
      S09ShotDefensePath.Reset();
    }
    if (HasPlan(TEXT("nodefense"))) {
      if (!S09ShotDir.IsEmpty() && !bS09ShotDefense) {
        bS09ShotDefense = true;
        S09ShotDefensePath = S09ShotDir / TEXT("s09-combat-defense-open.png");
        ShotDefenseAtElapsed = Elapsed;
        FS08Trace::Write(TEXT("S09AUTO defense-window shot"));
        TakeEvidenceShot(S09ShotDefensePath);
        return;
      }
      FS08Trace::Write(TEXT("S09AUTO no-defense"));
      NoDefenseCommand();
    } else if (HasPlan(TEXT("defend"))) {
      if (!S09ShotDir.IsEmpty() && !bS09ShotDefense) {
        bS09ShotDefense = true;
        S09ShotDefensePath = S09ShotDir / TEXT("s09-combat-defense-open.png");
        ShotDefenseAtElapsed = Elapsed;
        FS08Trace::Write(TEXT("S09AUTO defense-window shot"));
        TakeEvidenceShot(S09ShotDefensePath);
        return;
      }
      // First legal defense card for the attacked fighter.
      const FS09PlayerPanel* Own = Hud.ViewerPanel();
      if (!Own) return;
      bool bPicked = false;
      FString Reason;
      for (const FS09CardView& Card : Own->Cards) {
        if (!Card.bHidden &&
            CommandUi.ToggleDefenseCard(Card.InstanceId, Snap, Fighters, Reason)) {
          bPicked = true;
          FS08Trace::Write(TEXT("S09AUTO defense card picked"));
          break;
        }
      }
      if (!bPicked) {
        FS08Trace::Write(TEXT("S09AUTO no legal defense card - falling back to no-defense"));
        NoDefenseCommand();
        return;
      }
      ConfirmCombat();
    }
    return; // window belongs to a human otherwise
  }
  if (CommandUi.Mode == ES09CommandMode::CombatResolve) {
    // Reveal-state capture (GD-033): after the reveal the resolve window
    // shows BOTH committed cards + values; grab it before anyone resolves.
    if (!S09ShotDir.IsEmpty() && CommandUi.Combat.bRevealed && !bS09ShotResolveRevealed) {
      bS09ShotResolveRevealed = true;
      S09ShotResolveRevealedPath = S09ShotDir / TEXT("s09-combat-resolve-revealed.png");
      ShotResolveAtElapsed = Elapsed; // fresh 12s budget for THIS capture
      FS08Trace::Write(TEXT("S09AUTO resolve-revealed shot"));
      TakeEvidenceShot(S09ShotResolveRevealedPath);
      return;
    }
    if (!S09ShotResolveRevealedPath.IsEmpty() &&
        !FPaths::FileExists(S09ShotResolveRevealedPath)) {
      if (ShotResolveAtElapsed < 0.0f) ShotResolveAtElapsed = Elapsed;
      if (Elapsed < ShotResolveAtElapsed + 12.0f) return;
      FS08Trace::Write(TEXT("S09AUTO resolve-revealed shot file never appeared - proceeding WITHOUT the shot"));
      S09ShotResolveRevealedPath.Reset();
    }
    // The other seat's pending head blocks resolve HERE too (the same server
    // gate 'Resolve the pending choice first') - capture the blocked resolve
    // window once per head so evidence covers the non-owning seat during the
    // owner's reveal pause (BOOST_CHOICE hold).
    if (CommandUi.PendingQueue.Num() > 0) {
      const FString BlockedType = CommandUi.PendingQueue[0].Type;
      const FString BlockedKey =
          FString::Printf(TEXT("blocked:%s:%s"), *BlockedType,
                          *CommandUi.PendingQueue[0].Id);
      if (!S09ShotDir.IsEmpty() && !S09PendingShotKeys.Contains(BlockedKey)) {
        S09PendingShotKeys.Add(BlockedKey);
        S09ShotBlockedPath =
            S09ShotDir / FString::Printf(TEXT("s09-resolve-blocked-%s.png"), *BlockedType);
        ShotBlockedAtElapsed = Elapsed;
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO resolve-blocked shot (type=%s)"), *BlockedType));
        TakeEvidenceShot(S09ShotBlockedPath);
        return;
      }
      if (!S09ShotBlockedPath.IsEmpty() &&
          !FPaths::FileExists(S09ShotBlockedPath)) {
        if (ShotBlockedAtElapsed < 0.0f || Elapsed < ShotBlockedAtElapsed + 12.0f) return;
        FS08Trace::Write(TEXT("S09AUTO resolve-blocked shot file never appeared - proceeding WITHOUT the shot"));
        S09ShotBlockedPath.Reset();
      }
    }
    if (CommandUi.Combat.bRevealed) {
      // The reveal already ran server-side (this seat's earlier resolve, or
      // the other seat's): the combat is completing - a second resolveCombat
      // from here would only produce a spurious server rejection.
      return;
    }
    if (HasPlan(TEXT("resolve"))) {
      if (!S09ShotDir.IsEmpty() && !bS09ShotResolve) {
        bS09ShotResolve = true;
        S09ShotResolvePath = S09ShotDir / TEXT("s09-combat-resolve-window.png");
        FS08Trace::Write(TEXT("S09AUTO resolve-window shot"));
        TakeEvidenceShot(S09ShotResolvePath);
        return;
      }
      if (!S09ShotResolvePath.IsEmpty() && !FPaths::FileExists(S09ShotResolvePath)) {
        if (ShotResolveAtElapsed < 0.0f) ShotResolveAtElapsed = Elapsed;
        if (Elapsed < ShotResolveAtElapsed + 12.0f) return;
        FS08Trace::Write(TEXT("S09AUTO resolve shot file never appeared - proceeding WITHOUT the shot"));
        S09ShotResolvePath.Reset();
      }
      FS08Trace::Write(TEXT("S09AUTO resolve"));
      ResolveCombatCommand();
    }
    return;
  }
  if (CommandUi.Mode == ES09CommandMode::PendingChoice) {
    // GD-035: auto-answer ANY viewer-owned queue head so the two-client
    // pipeline cannot stall. Deterministic first-legal pick per type;
    // optional heads with no legal pick decline.
    const FString& Type = CommandUi.PendingChoice.Type;
    // One shot per distinct head VARIETY (type + stage + mode): the first
    // CHOOSE_SPACE head AND its stage-2 replacement both land in evidence
    // (s09-pending-<TYPE>[-sN][-MODE].png), not just the first head ever.
    if (!S09ShotDir.IsEmpty()) {
      const FString ShotKey = FString::Printf(TEXT("%s:%d:%s"), *Type,
                                              CommandUi.PendingChoice.Stage,
                                              *CommandUi.PendingChoice.Mode);
      if (!S09PendingShotKeys.Contains(ShotKey)) {
        S09PendingShotKeys.Add(ShotKey);
        FString ShotName = FString::Printf(TEXT("s09-pending-%s"), *Type);
        if (CommandUi.PendingChoice.Stage > 1) {
          ShotName += FString::Printf(TEXT("-s%d"), CommandUi.PendingChoice.Stage);
        }
        if (!CommandUi.PendingChoice.Mode.IsEmpty()) {
          ShotName += TEXT("-") + CommandUi.PendingChoice.Mode;
        }
        S09ShotPendingPath = S09ShotDir / (ShotName + TEXT(".png"));
        ShotPendingAtElapsed = Elapsed;
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO pending-open shot (type=%s stage=%d mode=%s)"), *Type,
            CommandUi.PendingChoice.Stage, *CommandUi.PendingChoice.Mode));
        TakeEvidenceShot(S09ShotPendingPath);
        return;
      }
    }
    if (!S09ShotPendingPath.IsEmpty() && !FPaths::FileExists(S09ShotPendingPath)) {
      if (ShotPendingAtElapsed < 0.0f || Elapsed < ShotPendingAtElapsed + 12.0f) return;
      FS08Trace::Write(TEXT("S09AUTO pending shot file never appeared - proceeding WITHOUT the shot"));
      S09ShotPendingPath.Reset();
    }
    if (Type == TEXT("BOOST_CHOICE")) {
      // GD-033: hold the boost answer a few seconds - an instant reply closes
      // the post-reveal pause before the OTHER seat's reveal capture frame
      // lands. Per-head hold; the pending deadlines dwarf 4s.
      if (S09BoostHoldKey != CommandUi.PendingChoice.Id) {
        S09BoostHoldKey = CommandUi.PendingChoice.Id;
        S09BoostHoldUntil = Elapsed + 4.0f;
        FS08Trace::Write(TEXT("S09AUTO boost choice - holding 4s for the other seat's reveal capture"));
      }
      if (Elapsed < S09BoostHoldUntil) return;
    }
    FString Reason;
    bool bPicked = false;
    const FS09PlayerPanel* Own = Hud.ViewerPanel();
    if (Type == TEXT("MOVE") || Type == TEXT("PLACE") || Type == TEXT("CHOOSE_SPACE")) {
      TArray<FString> LegalFighters;
      CommandUi.PendingLegalFighters(Fighters, LegalFighters);
      if ((Type == TEXT("MOVE") || Type == TEXT("PLACE")) && LegalFighters.Num() > 0) {
        for (const FString& FighterId : LegalFighters) {
          if (!CommandUi.SelectPendingFighter(FighterId, Snap, Fighters, Reason)) continue;
          const TSet<uint64> Cells =
              CommandUi.ComputePendingCells(Snap, BoardModel, Fighters);
          for (const uint64& Key : Cells) {
            const int32 X = static_cast<int32>(Key >> 32);
            const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
            if (CommandUi.SelectPendingCell(X, Y, Snap, BoardModel, Fighters, Reason)) {
              bPicked = true;
              break;
            }
          }
          if (bPicked) break;
          // Fighter without a legal cell: skip it (a later pending may revive).
          CommandUi.PendingFighterId.Reset();
        }
      } else {
        // CHOOSE_SPACE (both stages): first legal cell.
        const TSet<uint64> Cells =
            CommandUi.ComputePendingCells(Snap, BoardModel, Fighters);
        for (const uint64& Key : Cells) {
          const int32 X = static_cast<int32>(Key >> 32);
          const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
          if (CommandUi.SelectPendingCell(X, Y, Snap, BoardModel, Fighters, Reason)) {
            bPicked = true;
            break;
          }
        }
      }
    } else if (Type == TEXT("TARGET_FIGHTER")) {
      TArray<FString> LegalFighters;
      CommandUi.PendingLegalFighters(Fighters, LegalFighters);
      for (const FString& FighterId : LegalFighters) {
        if (CommandUi.SelectPendingFighter(FighterId, Snap, Fighters, Reason)) {
          bPicked = true;
          break;
        }
      }
    } else if (Type == TEXT("CHOOSE_ONE")) {
      if (CommandUi.SelectPendingOption(0, Reason)) bPicked = true;
    } else if (Type == TEXT("DECK_TOP_PICK") || Type == TEXT("DISCARD_CARDS") ||
               Type == TEXT("BOOST_CHOICE")) {
      // Exact-count card head: the picks must ACCUMULATE the required number
      // of distinct ids BEFORE one confirm (the old single-card probe could
      // never satisfy value > 1 - every confirm failed and un-picked). The
      // legality gates stay server-side + ConfirmPendingChoice; this driver
      // only orders the ids.
      TArray<FString> Pool;
      int32 Need = 0;
      if (CommandUi.PendingCardPickPlan(Snap, Pool, Need) && Need > 0 &&
          Pool.Num() >= Need) {
        TArray<FString> PickedIds;
        for (const FString& Id : Pool) {
          if (PickedIds.Num() >= Need) break;
          if (CommandUi.TogglePendingCard(Id, Snap, Reason)) PickedIds.Add(Id);
        }
        if (PickedIds.Num() == Need) {
          FS09PendingChoiceCommand Probe;
          if (CommandUi.ConfirmPendingChoice(Snap, false, Probe, Reason)) {
            bPicked = true;
          } else {
            const FString PickFail = Reason;
            for (const FString& Id : PickedIds) {
              CommandUi.TogglePendingCard(Id, Snap, Reason); // un-pick
            }
            // Once per head: a stable confirm rejection would re-log on every
            // tick otherwise (the same rate limit the stuck branch uses).
            if (S09PendingWaitTraceKey != CommandUi.PendingChoice.Id) {
              S09PendingWaitTraceKey = CommandUi.PendingChoice.Id;
              FS08Trace::Write(FString::Printf(
                  TEXT("S09AUTO pending pick plan rejected by confirm (type=%s): %s"),
                  *Type, *PickFail));
            }
          }
        } else {
          for (const FString& Id : PickedIds) {
            CommandUi.TogglePendingCard(Id, Snap, Reason); // un-pick
          }
        }
      }
    } else {
      FS08Trace::Write(FString::Printf(
          TEXT("S09AUTO pending type %s has no auto driver - waiting"), *Type));
      return;
    }
    if (bPicked) {
      // Bounded retries: the SAME head still being open after several
      // ACTUALLY DISPATCHED answers means the server keeps rejecting the
      // answer (or the mutation is lost) - stop, log ONCE, let the head stay
      // visibly blocked for the report instead of flooding retries.
      // S10 review P1(1): the budget is consumed ONLY on a real dispatch - a
      // gate-blocked tick (stream reconnecting, recovery lock) leaves the
      // budget intact, so four blocked ticks can no longer permanently hold
      // a head that was never answered.
      S09PendingAutoBudget.Observe(CommandUi.PendingChoice.Id);
      if (S09PendingAutoBudget.Exhausted()) {
        if (S09PendingWaitTraceKey != CommandUi.PendingChoice.Id) {
          S09PendingWaitTraceKey = CommandUi.PendingChoice.Id;
          FS08Trace::Write(FString::Printf(
              TEXT("S09AUTO pending head %s stayed open after %d dispatched auto-answers (type=%s) - holding (bounded)"),
              *CommandUi.PendingChoice.Id, S09PendingAutoBudget.Max, *Type));
        }
        return;
      }
      if (FS09AutoDraftTransitions::PendingAutoAnswer(ConfirmCombat(),
                                                     S09PendingAutoBudget)) {
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO pending picked (type=%s stage=%d)"), *Type,
            CommandUi.PendingChoice.Stage));
      }
      // Gate-blocked send: no attempt counted, no mode change, no "sent"
      // trace - the pick stays intact and the next tick retries.
    } else if (CommandUi.PendingChoice.bOptional) {
      // Same once-per-head rate limit as the stuck branch: a rejected decline
      // used to re-log on every tick until the server deadline closed it.
      if (CommandUi.PendingChoice.Id != S09PendingWaitTraceKey) {
        S09PendingWaitTraceKey = CommandUi.PendingChoice.Id;
        FS08Trace::Write(FString::Printf(TEXT("S09AUTO pending declined (type=%s)"), *Type));
      }
      DeclinePendingChoiceCommand();
    } else {
      // Mandatory head with no legal pick: log ONCE per head id (the stuck
      // choice stays visibly blocked; the old per-tick line flooded a 9.7 MB
      // trace in the GD-035 capture).
      const FString WaitKey = CommandUi.PendingChoice.Id;
      if (WaitKey != S09PendingWaitTraceKey) {
        S09PendingWaitTraceKey = WaitKey;
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO mandatory pending without a legal pick (type=%s id=%s) - waiting"),
            *Type, *WaitKey));
      }
    }
    return;
  }
  // attack plan: strike the first legal adjacent pair before maneuvering.
  if (HasPlan(TEXT("attack")) && Hud.bViewerTurn && CommandUi.Mode == ES09CommandMode::None &&
      (Snap.Phase == TEXT("ACTION_MANEUVER") || Snap.Phase == TEXT("ACTION_ATTACK")) &&
      FS08Contracts::PendingManeuverId(Snap).IsEmpty() && Hud.ActionsRemaining > 0) {
    // S10 review P1(5): bounded per-turn attack retries. Every definitive
    // server rejection of a dispatched attack (OnCommandRejected -> the
    // handler below) closes the draft and counts here; a fresh turn opens a
    // new window. Exhausted = skip attacks this turn, fall through to the
    // maneuver plan (the duel keeps progressing, no retry flood).
    const FString AttackBudgetKey = FString::Printf(TEXT("turn-%d"), Snap.TurnCount);
    S09AttackAutoBudget.Observe(AttackBudgetKey);
    FString Reason;
    const bool bAttackBudgetLeft = !S09AttackAutoBudget.Exhausted();
    if (!bAttackBudgetLeft) {
      if (S09AttackRejectTraceKey != AttackBudgetKey) {
        S09AttackRejectTraceKey = AttackBudgetKey;
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO attack retries exhausted for turn %d (%d definitive rejections) - falling through to maneuvers"),
            Snap.TurnCount, S09AttackAutoBudget.Max));
      }
    } else if (CommandUi.CanOpenAttackDraft(Snap, Reason)) {
      // P1 regression (packaged run 2026-09-27 14:42:59, seq1 stall): the
      // driver used to enter the draft while the controller's command gate was
      // still closed, log "ATTACK sent", flip the mode and stall the seat for
      // the rest of the run. Entering the draft requires the gate OPEN.
      FString GateReason;
      if (!Flow->CanIssueCombatCommand(GateReason)) {
        const FString WaitKey = TEXT("stream-gate-closed");
        if (S09PendingWaitTraceKey != WaitKey) {
          S09PendingWaitTraceKey = WaitKey;
          FS08Trace::Write(FString::Printf(
              TEXT("S09AUTO attack deferred - command gate closed (%s); retrying when the stream is ready"),
              *GateReason));
        }
        return;
      }
      S09PendingWaitTraceKey.Reset();
      CommandUi.Mode = ES09CommandMode::AttackDraft;
      const FS09PlayerPanel* Own = Hud.ViewerPanel();
      const FS09CardView* Chosen = nullptr;
      bool bChosenZoneTarget = false;
      // Melee pick first: a board-adjacent enemy (linked space; on a grid
      // manhattan 1 in the old order). ENV-O6: on an original-map board a
      // ranged attacker without an adjacent enemy takes the first enemy it
      // shares a zone with (server ranged rule). Grids keep the old
      // melee-only auto pick so the recorded Cobble / art-fixture S09AUTO
      // sequence stays unchanged; manual drafts offer ranged everywhere.
      // ENV-MAPS P5a opt-in 'ranged' token: zone-only picks go first (the
      // joiner's Merlin proof); without it the order is the old loop's.
      const bool bPreferRanged = HasPlan(TEXT("ranged"));
      const TArray<FS09CommandUi::FAutoAttackPick> Picks =
          FS09CommandUi::AutoAttackPicks(BoardModel, Fighters, CommandUi.ViewerId, bPreferRanged);
      for (const FS09CommandUi::FAutoAttackPick& Pick : Picks) {
        const FS08BoardFighter* Candidate = Fighters.FindByPredicate(
            [&Pick](const FS08BoardFighter& F) { return F.Id == Pick.AttackerId; });
        const FS08BoardFighter* Target = Fighters.FindByPredicate(
            [&Pick](const FS08BoardFighter& F) { return F.Id == Pick.TargetId; });
        if (!Candidate || !Target) continue;
        FString Why;
        if (!CommandUi.SelectAttacker(Candidate->Id, BoardModel, Fighters, Why)) continue;
        if (!CommandUi.SelectTarget(Target->Id, BoardModel, Fighters, Why)) continue;
        bChosenZoneTarget = Pick.bZoneOnly;
        if (Pick.bZoneOnly) {
          FS08Trace::Write(FString::Printf(
              TEXT("S09AUTO ranged target attacker=%s at=%s target=%s at=%s via=shared-zone (not linked)%s"),
              *Candidate->Id, *BoardModel.CellLabel(Candidate->X, Candidate->Y), *Target->Id,
              *BoardModel.CellLabel(Target->X, Target->Y),
              bPreferRanged ? TEXT(" prefer=ranged") : TEXT("")));
        }
        if (!Own) break;
        // Prefer a "You may BOOST this attack" card (Second Shot / Noble
        // Sacrifice): after the reveal the server pauses on the owner's
        // BOOST_CHOICE, which is exactly the post-reveal window the GD-033
        // reveal proof needs to capture on the OTHER seat. Purely a pick
        // order among equally legal cards - the server stays authoritative.
        for (const FS09CardView& Card : Own->Cards) {
          if (Card.bHidden) continue;
          const bool bMayBoost =
              Card.Name == TEXT("Second Shot") || Card.Name == TEXT("Noble Sacrifice");
          if (!bMayBoost && Chosen) continue;
          // ToggleAttackCard REPLACES the pick (AttackCardId = id). The old
          // code toggled the previous card off AFTERWARDS - but that call
          // re-SELECTED it (AttackCardId was no longer equal to it), so the
          // boost-capable card was silently dropped for the earlier pick.
          if (!CommandUi.ToggleAttackCard(Card.InstanceId, Snap, Fighters, Reason)) continue;
          Chosen = &Card;
          if (bMayBoost) break;
        }
        break;
      }
      const bool bChoseMayBoost =
          Chosen && (Chosen->Name == TEXT("Second Shot") ||
                     Chosen->Name == TEXT("Noble Sacrifice"));
      // 'ranged' plan token: a zone-only (ranged) attack is the proof itself
      // and is never parked for a may-boost card.
      const bool bRangedProofPick = bPreferRanged && bChosenZoneTarget && Chosen;
      if (!bChoseMayBoost && !bRangedProofPick && !bS09ShotResolveRevealed && OwnTurnIndex < 8 &&
          Elapsed < 150.0f) {
        // The GD-033 reveal proof needs a may-boost attack (the server pauses
        // after THAT reveal). While no such card is in hand, close the draft
        // and keep maneuvering - draw closer to it. Fallback after 8 own turns
        // / 150s attacks with whatever is legal so the demo still runs.
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO attack deferred - no may-boost card in hand (turn#%d elapsed=%.0fs)"),
            OwnTurnIndex, Elapsed));
        if (Chosen) {
          CommandUi.ToggleAttackCard(Chosen->InstanceId, Snap, Fighters, Reason);
        }
        CommandUi.Mode = ES09CommandMode::None;
        CommandUi.AttackAttackerId.Reset();
        CommandUi.AttackTargetId.Reset();
        CommandUi.AttackCardId.Reset();
      }
      if (!CommandUi.AttackAttackerId.IsEmpty() && !CommandUi.AttackTargetId.IsEmpty() &&
          !CommandUi.AttackCardId.IsEmpty()) {
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO attack (attacker=%s target-set card-set)"),
            *CommandUi.AttackAttackerId));
        if (!ConfirmCombat()) {
          // Gate closed between the pre-entry check and the confirm (e.g. the
          // stream died mid-pick): back out of the draft and retry later
          // instead of parking in mode=AttackDraft forever.
          CommandUi.Mode = ES09CommandMode::None;
          CommandUi.AttackAttackerId.Reset();
          CommandUi.AttackTargetId.Reset();
          CommandUi.AttackCardId.Reset();
          NextCommandAt = Elapsed + 1.0f;
        }
      } else {
        // No legal pair: close the draft and fall through to maneuvering.
        CommandUi.Mode = ES09CommandMode::None;
        CommandUi.AttackAttackerId.Reset();
        CommandUi.AttackTargetId.Reset();
        CommandUi.AttackCardId.Reset();
      }
    }
  }
  if (CommandUi.Mode == ES09CommandMode::AttackDraft) return;
  // scheme plan: one scheme card in the next own action phase. Prefer a
  // MULTI-STAGE scheme (Restless Spirits: the CHOOSE_SPACE stage1->stage2
  // pair the pending evidence needs) - purely a pick order among equally
  // legal schemes; the server stays authoritative.
  if (HasPlan(TEXT("scheme")) && Hud.bViewerTurn && CommandUi.Mode == ES09CommandMode::None &&
      (Snap.Phase == TEXT("ACTION_MANEUVER") || Snap.Phase == TEXT("ACTION_ATTACK")) &&
      Hud.ActionsRemaining > 0) {
    const FS09PlayerPanel* Own = Hud.ViewerPanel();
    if (Own) {
      // LEGALITY FIRST (10:41 loop): a named banner whose fighter is dead is
      // rejected by the server - never re-send it. Among the legal schemes
      // prefer Restless Spirits (the CHOOSE_SPACE stage1->stage2 evidence).
      const FS09CardView* Fallback = nullptr;
      for (const FS09CardView& Card : Own->Cards) {
        if (Card.bHidden || Card.CardType != TEXT("SCHEME")) continue;
        if (!FS09CommandUi::SchemePlayableByLivingFighters(Card, Fighters,
                                                           CommandUi.ViewerId)) {
          continue;
        }
        if (Card.Name == TEXT("Restless Spirits")) {
          Fallback = &Card;
          break;
        }
        if (!Fallback) Fallback = &Card;
      }
      if (Fallback) {
        if (Flow->PlayScheme(Fallback->InstanceId)) {
          FS08Trace::Write(TEXT("S09AUTO scheme"));
          NextCommandAt = Elapsed + 1.2f;
        }
        // Blocked scheme: no advance, no log - the next tick retries once the
        // command gate reopens (the controller already traces the block).
        return;
      }
    }
  }

  if (CommandUi.Mode == ES09CommandMode::DiscardDraft) {
    // Let the evidence shot capture the open overlay before confirming. The
    // UI capture writes a few frames after the request: also hold until the
    // file actually exists, or the shot lands on the closed state.
    if (!S09ShotDir.IsEmpty() && ShotDiscardAtElapsed >= 0.0f && !bS09ShotDiscard) return;
    if (!S09ShotDir.IsEmpty() && bS09ShotDiscard && !S09ShotDiscardPath.IsEmpty() &&
        !FPaths::FileExists(S09ShotDiscardPath)) {
      if (Elapsed < ShotDiscardAtElapsed + 12.0f) return;
      FS08Trace::Write(TEXT("S09AUTO discard shot file never appeared - proceeding WITHOUT the shot"));
      S09ShotDiscardPath.Reset();
    }
    // Drive the exact-count discard: pick the first N own hand instances.
    const FS09PlayerPanel* Own = Hud.ViewerPanel();
    if (!Own) return;
    int32 Added = 0;
    FString Reason;
    for (const FS09CardView& Card : Own->Cards) {
      if (CommandUi.DiscardSelection.Num() >= CommandUi.PendingDiscard.Count) break;
      if (CommandUi.ToggleDiscardCard(Card.InstanceId, Snap, Reason)) ++Added;
    }
    if (Added == 0 && CommandUi.DiscardSelection.Num() < CommandUi.PendingDiscard.Count) {
      FS08Trace::Write(TEXT("S09AUTO discard could not reach the required count"));
      return;
    }
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO discard picks=%d"), CommandUi.DiscardSelection.Num()));
    ConfirmDraft();
    return;
  }

  if (CommandUi.Mode == ES09CommandMode::ManeuverDraft) {
    // Coverage plan per own turn/action. beginManeuver already SPENT the
    // action, so inside the draft ActionsDone = 2 - actionsRemaining counts
    // this action as done (first draft of a turn = 1):
    //   turn 1 action 1: host = ZERO moves (draw only); boost variant boosts
    //   the freshly drawn (bNew) card and also confirms zero moves;
    //   turn 1 action 2 / turn 2: hero one step; host turn 2 action 1 also
    //   moves a SECOND fighter (multi-fighter maneuver).
    const int32 ActionsDone = Hud.ActionsRemaining >= 0 ? 2 - Hud.ActionsRemaining : 1;
    const bool bZeroMove =
        OwnTurnIndex == 1 && ActionsDone == 1 && CommandUi.Moves.Num() == 0;
    if (bZeroMove && bAutoS09Boost) {
      const FS09PlayerPanel* Own = Hud.ViewerPanel();
      const FS09CardView* NewCard = nullptr;
      int32 NewCount = 0;
      if (Own) {
        for (const FS09CardView& Card : Own->Cards) {
          if (Card.bNew && !Card.bHidden) {
            ++NewCount;
            if (!NewCard) NewCard = &Card;
          }
        }
      }
      if (NewCount == 0) {
        FS08Trace::Write(FString::Printf(
            TEXT("S09AUTO boost skipped: no bNew card (panel=%d cards=%d)"),
            Own ? 1 : 0, Own ? Own->Cards.Num() : -1));
      } else if (NewCard && CommandUi.BoostCardId != NewCard->InstanceId) {
        FString Reason;
        if (CommandUi.ToggleBoostCard(NewCard->InstanceId, Snap, Reason)) {
          FS08Trace::Write(FString::Printf(TEXT("S09AUTO boost(new card) set (B%d)"),
                                           NewCard->BoostValue));
        } else {
          FS08Trace::Write(FString::Printf(TEXT("S09AUTO boost toggle rejected: %s"), *Reason));
        }
      }
    }
    // First-draft evidence shot (P1): hold with the maneuver-draft overlay
    // open (marker visible) until the capture file exists - the UI capture
    // writes a few frames after the request.
    if (!S09ShotDir.IsEmpty() && !bS09ShotDraft) {
      if (ShotDraftAtElapsed < 0.0f) ShotDraftAtElapsed = Elapsed + 1.0f;
      if (Elapsed < ShotDraftAtElapsed) return;
      bS09ShotDraft = true;
      S09ShotDraftPath = S09ShotDir / TEXT("s09-maneuver-draft-open.png");
      FS08Trace::Write(TEXT("S09AUTO draft-open shot (maneuver marker live)"));
      TakeEvidenceShot(S09ShotDraftPath);
      return;
    }
    if (bS09ShotDraft && !S09ShotDraftPath.IsEmpty() &&
        !FPaths::FileExists(S09ShotDraftPath)) {
      if (Elapsed < ShotDraftAtElapsed + 12.0f) return;
      FS08Trace::Write(TEXT("S09AUTO draft shot file never appeared - proceeding"));
      S09ShotDraftPath.Reset();
    }
    if (!bZeroMove) {
      const FS08BoardFighter* Hero = nullptr;
      const FS08BoardFighter* Sidekick = nullptr;
      for (const FS08BoardFighter& Entry : Fighters) {
        if (Entry.OwnerId != CommandUi.ViewerId || !Entry.IsAlive()) continue;
        if (Entry.bIsHero && !Hero) Hero = &Entry;
        if (!Entry.bIsHero && !Sidekick) Sidekick = &Entry;
      }
      if (!Hero) return;
      if (HasPlan(TEXT("attack"))) {
        // Multi-step approach (stage 3 T5.2): the legal destination within the
        // hero's movement that is closest (terrain distance) to the NEAREST
        // living enemy - allies are pass-through, so a hero boxed in by its
        // own sidekicks and an obstacle still gets out (T.Rex art fixture,
        // T3.2 attempt). The former one-cell greedy step only tried the four
        // neighbours and parked the hero there for the whole game.
        CommandUi.SelectFighter(Hero->Id, Snap, BoardModel, Fighters);
        FIntPoint Dest(-1, -1);
        int32 FromDist = 0, ToDist = 0, Steps = 0;
        FString Reason;
        const bool bPicked = FS08BoardModel::PickApproachDestination(
            BoardModel, Fighters, Hero->Id, Hero->Movement, Dest, FromDist, ToDist, Steps);
        if (bPicked &&
            CommandUi.SetDestination(Hero->Id, Dest.X, Dest.Y, Snap, BoardModel, Fighters,
                                     Reason)) {
          FS08Trace::Write(FString::Printf(
              TEXT("S09AUTO approach fighter=%s from=(%d,%d) to=(%d,%d) steps=%d allowance=%d enemyDist=%d->%d"),
              *Hero->Id, Hero->X, Hero->Y, Dest.X, Dest.Y, Steps, Hero->Movement, FromDist, ToDist));
        } else if (bPicked) {
          FS08Trace::Write(FString::Printf(
              TEXT("S09AUTO approach: destination (%d,%d) refused by the draft (%s)"), Dest.X, Dest.Y,
              *Reason));
        } else {
          FS08Trace::Write(TEXT("S09AUTO approach: no improving legal step"));
        }
      } else {
        StepOneCell(CommandUi, Snap, BoardModel, Fighters, Hero->Id);
      }
      // ENV-MAPS P5a opt-in 'ranged' token: every own living RANGED sidekick
      // (Merlin) also moves - by the same graph rules (legal reach, links) -
      // to the nearest space from where it has a zone-only target (no linked
      // enemy, a shared zone), clear of the other draft endpoints. Stays put
      // when it already stands in such a position or none is reachable.
      FString RangedMovedId;
      if (HasPlan(TEXT("ranged"))) {
        TSet<uint64> Reserved;
        for (const FS09DraftMove& Move : CommandUi.Moves) {
          Reserved.Add(FS08BoardModel::CellKey(Move.DestX, Move.DestY));
        }
        for (const FS08BoardFighter& Entry : Fighters) {
          if (Entry.OwnerId != CommandUi.ViewerId || !Entry.IsAlive() || Entry.bIsHero) continue;
          if (!FS09CommandUi::IsRangedAttacker(Entry)) continue;
          FIntPoint Dest(-1, -1);
          int32 Steps = 0;
          FString ZoneTarget;
          if (!FS09CommandUi::PickRangedPosition(BoardModel, Fighters, Entry.Id, Entry.Movement, Reserved, Dest,
                                                 Steps, ZoneTarget)) {
            continue;
          }
          FString Reason;
          CommandUi.SelectFighter(Entry.Id, Snap, BoardModel, Fighters);
          if (CommandUi.SetDestination(Entry.Id, Dest.X, Dest.Y, Snap, BoardModel, Fighters, Reason)) {
            Reserved.Add(FS08BoardModel::CellKey(Dest.X, Dest.Y));
            if (RangedMovedId.IsEmpty()) RangedMovedId = Entry.Id;
            FS08Trace::Write(FString::Printf(
                TEXT("S09AUTO ranged position fighter=%s from=%s to=%s steps=%d zoneTarget=%s"), *Entry.Id,
                *BoardModel.CellLabel(Entry.X, Entry.Y), *BoardModel.CellLabel(Dest.X, Dest.Y), Steps,
                *ZoneTarget));
          } else {
            FS08Trace::Write(FString::Printf(TEXT("S09AUTO ranged position: destination %s refused by the draft (%s)"),
                                             *BoardModel.CellLabel(Dest.X, Dest.Y), *Reason));
          }
        }
      }
      const bool bMultiFighter = !bAutoS09Boost && OwnTurnIndex == 2 && ActionsDone == 1 && Sidekick &&
                                 Sidekick->Id != RangedMovedId;
      if (bMultiFighter) {
        StepOneCell(CommandUi, Snap, BoardModel, Fighters, Sidekick->Id);
        FS08Trace::Write(FString::Printf(TEXT("S09AUTO multi-fighter moves=%d"),
                                         CommandUi.Moves.Num()));
      }
    } else {
      FS08Trace::Write(TEXT("S09AUTO zero-move confirm (draw only, no movement)"));
    }
    ConfirmDraft();
    return;
  }

  if (!Hud.bViewerTurn) return;
  if (Hud.ActionsRemaining > 0 && !Snap.Phase.IsEmpty() &&
      Snap.Phase.StartsWith(TEXT("ACTION_")) &&
      FS08Contracts::PendingManeuverId(Snap).IsEmpty()) {
    BeginManeuverCommand();
  } else if (Hud.ActionsRemaining == 0 &&
             FS08FlowController::IsEndTurnPhase(Snap.Phase) &&
             FS08Contracts::PendingManeuverId(Snap).IsEmpty()) {
    EndTurnCommand();
  }
}

void AS08FlowGameMode::TakeS09Shots() {
  if (!bAutoS09 || !Flow.IsValid() || S09ShotDir.IsEmpty()) return;
  // W5b-R: the screen damage number must have painted at its place for >= 2 frames (geom=painted) before the frame;
  // at most 0.6 s later the frame is taken anyway (the number lives 0.9 s) and the trace says so.
  const bool bDamagePainted = !ArtHud.bTagsEnabled || ArtHud.DamageStableFrames >= 2;
  if (!bS09ShotDamage && DamageShotAtElapsed >= 0.0f && Elapsed >= DamageShotAtElapsed &&
      (bDamagePainted || Elapsed >= DamageShotAtElapsed + 0.6f) && !FScreenshotRequest::IsScreenshotRequested()) {
    bS09ShotDamage = true;
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO damage-number shot stableFrames=%d"), ArtHud.DamageStableFrames));
    TakeEvidenceShot(S09ShotDir / TEXT("s09-damage-number.png"));
  }
  if (!bS09ShotDamageCombat && DamageCombatShotAtElapsed >= 0.0f && Elapsed >= DamageCombatShotAtElapsed &&
      (ArtHud.DamageStableFrames >= 2 || Elapsed >= DamageCombatShotDeadline) &&
      !FScreenshotRequest::IsScreenshotRequested()) {
    bS09ShotDamageCombat = true;
    FS08Trace::Write(FString::Printf(TEXT("S09AUTO damage-combat shot fighter=%s stableFrames=%d"),
                                     *ArtHud.DamageFighterId, ArtHud.DamageStableFrames));
    TakeEvidenceShot(S09ShotDir / TEXT("s09-damage-combat.png"));
  }
  const FS08Snapshot& Snap = Flow->GetAppliedSnapshot();
  // Shot 1: first confirmed maneuver settled (begin+submit applied, HUD live).
  if (!bS09ShotHud && ShotHudAtElapsed < 0.0f && S09FirstConfirmSeq >= 0 &&
      Snap.SequenceNumber >= S09FirstConfirmSeq + 1 &&
      FS08Contracts::PendingManeuverId(Snap).IsEmpty()) {
    ShotHudAtElapsed = Elapsed + 1.0f;
  }
  if (!bS09ShotHud && ShotHudAtElapsed >= 0.0f && Elapsed >= ShotHudAtElapsed) {
    bS09ShotHud = true;
    TakeEvidenceShot(S09ShotDir / TEXT("s09-hud-after-first-maneuver.png"));
  }
  // Shot 2: the discard draft is open with the overlay visible.
  if (!bS09ShotDiscard && ShotDiscardAtElapsed < 0.0f &&
      CommandUi.Mode == ES09CommandMode::DiscardDraft) {
    ShotDiscardAtElapsed = Elapsed + 1.0f;
  }
  if (!bS09ShotDiscard && ShotDiscardAtElapsed >= 0.0f && Elapsed >= ShotDiscardAtElapsed) {
    bS09ShotDiscard = true;
    S09ShotDiscardPath = S09ShotDir / TEXT("s09-discard-open.png");
    TakeEvidenceShot(S09ShotDiscardPath);
  }
}

// ---- GD-032/033 backend-less packaged probe --------------------------------
// Proves the Slate HUD actually RENDERS in a packaged client: drives the
// captured fixture-04 host body through the real HUD model + command machine
// (no backend, no login), captures UI-inclusive shots of both overlay states
// and checks that a Slate-routed key event reaches the same handler chain
// the manual UI path uses.

namespace {
const TCHAR* S09ProbeHostId = TEXT("cmugykjjb0000wi9w2nq4qlkj");

// A captured gameState(gameId) response {"raw": <body object or string>}.
// W4-A -Bench reuses it for the Cobble scene (Config/Bench/S08BenchCobble.json,
// which adds benchViewerId / benchBoardId at the root).
bool S08LoadGameStateFixture(const FString& File, FS08Snapshot& Out, TSharedPtr<FJsonObject>* OutRoot = nullptr) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *File)) {
    return false;
  }
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  if (OutRoot) *OutRoot = *Root;
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Body)) {
    if (!FS08Contracts::TryParseJsonValue(Body, Value, Problem)) return false;
  } else if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FString RawState;
  FS08GraphQLError Error;
  return FS08Contracts::ParseGameStateQuery(Body, Out, RawState, Error);
}

bool S09ProbeLoadSnapshot(FS08Snapshot& Out) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return S08LoadGameStateFixture(FPaths::Combine(Dir, TEXT("04-game-state-query-host.json")), Out);
}

TSharedRef<FJsonObject> S09ProbeMeta(const FS08Snapshot& Snapshot) {
  return MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
}

void S09ProbeSetPendingManeuver(FS08Snapshot& Snapshot, const FString& Id) {
  const TSharedRef<FJsonObject> Meta = S09ProbeMeta(Snapshot);
  const TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), Id);
  Pending->SetStringField(TEXT("playerId"), S09ProbeHostId);
  Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
}

void S09ProbeSetPendingDiscard(FS08Snapshot& Snapshot, int32 Count) {
  const TSharedRef<FJsonObject> Meta = S09ProbeMeta(Snapshot);
  Meta->RemoveField(TEXT("pendingManeuver"));
  const TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), TEXT("discard:1:9"));
  Pending->SetStringField(TEXT("playerId"), S09ProbeHostId);
  Pending->SetNumberField(TEXT("count"), Count);
  Meta->SetObjectField(TEXT("pendingHandDiscard"), Pending);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
}

// Appends a fresh drawn instance (the beginManeuver draw) to the own hand.
void S09ProbeDrawCard(FS08Snapshot& Snapshot, const FString& DrawnId) {
  const TSharedRef<FJsonObject> Hands =
      MakeShared<FJsonObject>(*(Snapshot.HandZones->AsObject()));
  const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(S09ProbeHostId);
  const TSharedPtr<FJsonObject> Hand = HandValue.IsValid() ? HandValue->AsObject() : nullptr;
  if (!Hand.IsValid()) return;
  const TSharedRef<FJsonObject> NewHand = MakeShared<FJsonObject>(*Hand);
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!NewHand->TryGetArrayField(TEXT("cards"), Cards) || !Cards || Cards->Num() == 0) return;
  TArray<TSharedPtr<FJsonValue>> Grown = *Cards;
  const TSharedRef<FJsonObject> Drawn = MakeShared<FJsonObject>(*(*Cards)[0]->AsObject());
  Drawn->SetStringField(TEXT("id"), DrawnId);
  Grown.Add(MakeShared<FJsonValueObject>(Drawn));
  NewHand->SetArrayField(TEXT("cards"), Grown);
  Hands->SetObjectField(S09ProbeHostId, NewHand);
  Snapshot.HandZones = MakeShared<FJsonValueObject>(Hands);
}

// Drops every draft-opening pending: back to the quiet ACTION phase fixture.
void S09ProbeClearPending(FS08Snapshot& Snapshot) {
  const TSharedRef<FJsonObject> Meta = S09ProbeMeta(Snapshot);
  Meta->RemoveField(TEXT("pendingManeuver"));
  Meta->RemoveField(TEXT("pendingHandDiscard"));
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
}

// Scheme-picker scene hand: two LEGAL schemes (any banner + Harpy banner,
// both playable with the living fixture roster), one non-SCHEME card and one
// dead-banner scheme (Merlin lives on the OPPONENT side only) - the picker
// must accept exactly the two legal ones.
void S09ProbeSetSchemeHand(FS08Snapshot& Snapshot) {
  const TSharedRef<FJsonObject> Hands =
      MakeShared<FJsonObject>(*(Snapshot.HandZones->AsObject()));
  const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(S09ProbeHostId);
  const TSharedPtr<FJsonObject> Hand = HandValue.IsValid() ? HandValue->AsObject() : nullptr;
  if (!Hand.IsValid()) return;
  const TSharedRef<FJsonObject> NewHand = MakeShared<FJsonObject>(*Hand);
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!NewHand->TryGetArrayField(TEXT("cards"), Cards) || !Cards || Cards->Num() == 0) return;
  auto CloneCard = [Cards]() {
    return MakeShared<FJsonObject>(*(*Cards)[0]->AsObject());
  };
  auto Scheme = [&CloneCard](const FString& Id, const FString& Name,
                             const FString& Banner) {
    const TSharedRef<FJsonObject> Card = CloneCard();
    Card->SetStringField(TEXT("id"), Id);
    Card->SetStringField(TEXT("name"), Name);
    Card->SetStringField(TEXT("cardType"), TEXT("SCHEME"));
    Card->SetStringField(TEXT("bannerName"), Banner);
    return Card;
  };
  const TSharedRef<FJsonObject> Attack = CloneCard();
  Attack->SetStringField(TEXT("id"), TEXT("atk-plain::3"));
  Attack->SetStringField(TEXT("name"), TEXT("Clutching Claws"));
  Attack->SetStringField(TEXT("cardType"), TEXT("VERSATILE"));
  TArray<TSharedPtr<FJsonValue>> Rebuilt;
  Rebuilt.Add(MakeShared<FJsonValueObject>(
      Scheme(TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT(""))));
  Rebuilt.Add(MakeShared<FJsonValueObject>(
      Scheme(TEXT("sch-harpy::2"), TEXT("Winged Frenzy"), TEXT("Harpy"))));
  Rebuilt.Add(MakeShared<FJsonValueObject>(Attack));
  Rebuilt.Add(MakeShared<FJsonValueObject>(
      Scheme(TEXT("sch-dead::4"), TEXT("Forbidden Lore"), TEXT("Merlin"))));
  NewHand->SetArrayField(TEXT("cards"), Rebuilt);
  Hands->SetObjectField(S09ProbeHostId, NewHand);
  Snapshot.HandZones = MakeShared<FJsonValueObject>(Hands);
}
} // namespace

void AS08FlowGameMode::SimulateSlateKeyProbe(const FKey& Key, bool bUp) {
  if (!GEngine || !GEngine->GameViewport) {
    FS08Trace::Write(TEXT("S09PROBE key sim: no game viewport"));
    return;
  }
  FSlateApplication& App = FSlateApplication::Get();
  // Route like real hardware: focus the game viewport widget so the event
  // tunnels through Slate into UGameViewportClient::InputKey ->
  // PlayerController input -> the same WasInputKeyJustPressed handlers the
  // manual UI path uses.
  TSharedPtr<SViewport> Viewport = GEngine->GameViewport->GetGameViewportWidget();
  if (!Viewport.IsValid()) {
    FS08Trace::Write(TEXT("S09PROBE key sim: viewport widget missing"));
    return;
  }
  App.SetKeyboardFocus(Viewport.ToSharedRef(), EFocusCause::SetDirectly);
  const FName KeyName = Key.GetFName();
  if (bUp) {
    const FKeyEvent Up(Key, FModifierKeysState(), 0, false, 0, 0);
    App.ProcessKeyUpEvent(Up);
    FS08Trace::Write(FString::Printf(TEXT("S09PROBE slate key %s up sent"), *KeyName.ToString()));
  } else {
    // Arm the route attribution so the handler run on the next tick counts
    // as the REAL Slate path (not the direct InputKey fallback).
    S09KeyRouteArmed = 1;
    const FKeyEvent Down(Key, FModifierKeysState(), 0, false, 0, 0);
    const bool bHandled = App.ProcessKeyDownEvent(Down);
    FS08Trace::Write(FString::Printf(TEXT("S09PROBE slate key %s down sent (handled=%d)"),
                                     *KeyName.ToString(), bHandled ? 1 : 0));
  }
}

void AS08FlowGameMode::RunS09HudProbe() {
  const int32 Step = S09ProbeStep;
  if (Step == 0) {
    if (!S09ProbeLoadSnapshot(S09ProbeSnapshot)) {
      FS08Trace::Write(TEXT("S09PROBE fixture load FAILED - exiting"));
      FS08Trace::Close();
      FGenericPlatformMisc::RequestExit(false);
      return;
    }
    if (!FS08BoardModel::DecodeFighters(S09ProbeSnapshot.Fighters, Fighters) ||
        !BoardModel.Decode(S09ProbeSnapshot.BoardState)) {
      FS08Trace::Write(TEXT("S09PROBE fighters/board decode FAILED - exiting"));
      FS08Trace::Close();
      FGenericPlatformMisc::RequestExit(false);
      return;
    }
    // Negative-control frame FIRST: the 3D board renders with the HUD hidden
    // (Hud.bValid false) - this capture MUST fail every state gate later.
    SyncBoardFromApplied();
    RefreshHud();
    FS08Trace::Write(
        TEXT("S09PROBE markers maneuver=#FF00FF discard=#00FFFF (draft panels only)"));
    FS08Trace::Write(TEXT("S09PROBE board-only view live (HUD hidden - negative control)"));
    TakeEvidenceShot(S09ProbeDir / TEXT("s09-probe-board-only.png"));
    S09ProbeStep = 1;
    S09ProbeNextAt = Elapsed + 5.0f;
    return;
  }
  if (Step == 1) {
    // Hold until the negative-control capture exists, then build the draft.
    if (!FPaths::FileExists(S09ProbeDir / TEXT("s09-probe-board-only.png"))) {
      if (Elapsed < S09ProbeNextAt) return;
      FS08Trace::Write(TEXT("S09PROBE board-only shot never appeared - exiting"));
      FS08Trace::Close();
      FGenericPlatformMisc::RequestExit(false);
      return;
    }
    // Quiet-state baseline hand -> previous-hand set (as HandleApplied does).
    FS09HudModel Baseline;
    Baseline.Build(S09ProbeSnapshot, S09ProbeHostId, TSet<FString>(),
                   S09ProbeSnapshot.SequenceNumber, S09ProbeSnapshot.SequenceNumber);
    if (const FS09PlayerPanel* Own = Baseline.ViewerPanel()) {
      for (const FS09CardView& Card : Own->Cards) {
        S09ProbePreviousIds.Add(Card.InstanceId);
      }
    }
    // beginManeuver committed: hand grows to 6 with the drawn instance and a
    // pending maneuver opens the draft (boost = the *new* card, as the demo).
    S09ProbeDrawCard(S09ProbeSnapshot, TEXT("drawn-new::9"));
    S09ProbeSetPendingManeuver(S09ProbeSnapshot, TEXT("maneuver:1:5"));
    CommandUi.ViewerId = S09ProbeHostId;
    CommandUi.OnSnapshot(S09ProbeSnapshot, BoardModel, Fighters);
    Hud.Build(S09ProbeSnapshot, S09ProbeHostId, S09ProbePreviousIds,
              S09ProbeSnapshot.SequenceNumber, S09ProbeSnapshot.SequenceNumber);
    FString Reason;
    CommandUi.ToggleBoostCard(TEXT("drawn-new::9"), S09ProbeSnapshot, Reason);
    SyncBoardFromApplied(); // 3D board behind the HUD
    RefreshHud();
    FS08Trace::Write(TEXT("S09PROBE maneuver-draft view live (hand=6, new=drawn-new::9, boost set)"));
    S09ProbeStep = 2;
    S09ProbeNextAt = Elapsed + 1.5f;
    return;
  }
  if (Step == 2) {
    if (Elapsed < S09ProbeNextAt) return;
    TakeEvidenceShot(S09ProbeDir / TEXT("s09-probe-maneuver-draft.png"));
    S09ProbeStep = 3;
    S09ProbeNextAt = Elapsed + 5.0f;
    return;
  }
  if (Step == 3) {
    if (!FPaths::FileExists(S09ProbeDir / TEXT("s09-probe-maneuver-draft.png"))) {
      if (Elapsed < S09ProbeNextAt) return;
      FS08Trace::Write(TEXT("S09PROBE shot1 file never appeared - exiting"));
      FS08Trace::Close();
      FGenericPlatformMisc::RequestExit(false);
      return;
    }
    // Discard overlay: pendingHandDiscard count=2 replaces the maneuver.
    CommandUi.BoostCardId.Reset();
    S09ProbeSetPendingDiscard(S09ProbeSnapshot, 2);
    CommandUi.OnSnapshot(S09ProbeSnapshot, BoardModel, Fighters);
    Hud.Build(S09ProbeSnapshot, S09ProbeHostId, S09ProbePreviousIds,
              S09ProbeSnapshot.SequenceNumber, S09ProbeSnapshot.SequenceNumber);
    RefreshHud();
    S09ProbePickCount = CommandUi.DiscardSelection.Num();
    FS08Trace::Write(FString::Printf(TEXT("S09PROBE discard overlay live (count=2, picks=%d)"),
                                     S09ProbePickCount));
    S09ProbeStep = 4;
    S09ProbeNextAt = Elapsed + 1.5f;
    return;
  }
  if (Step == 4) {
    if (Elapsed < S09ProbeNextAt) return;
    TakeEvidenceShot(S09ProbeDir / TEXT("s09-probe-discard-open.png"));
    SimulateSlateKeyProbe(EKeys::One, /*bUp=*/false);
    S09ProbeStep = 5;
    S09ProbeNextAt = Elapsed + 1.0f;
    return;
  }
  if (Step == 5) {
    SimulateSlateKeyProbe(EKeys::One, /*bUp=*/true);
    S09ProbeStep = 6;
    S09ProbeNextAt = Elapsed + 1.0f;
    return;
  }
  if (Step == 6) {
    if (S09SlateKeySeen == 0) {
      // The real Slate route did not reach the handler chain - retry through
      // the engine input entry (below Slate) as a SEPARATE fallback verdict.
      if (auto* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr) {
        FS08Trace::Write(
            TEXT("S09PROBE slate route unseen - retry via PlayerController InputKey"));
        FViewport* Viewport = GEngine && GEngine->GameViewport
                                  ? GEngine->GameViewport->Viewport
                                  : nullptr;
        if (Viewport) {
          S09KeyRouteArmed = 2;
          PC->InputKey(FInputKeyEventArgs(Viewport, INPUTDEVICEID_NONE, EKeys::One,
                                          IE_Pressed, 1.0f, false,
                                          FPlatformTime::Cycles()));
        } else {
          FS08Trace::Write(TEXT("S09PROBE viewport handle missing - input retry skipped"));
        }
      }
      S09ProbeStep = 7;
      S09ProbeNextAt = Elapsed + 1.0f;
      return;
    }
    S09ProbeStep = 8;
    return;
  }
  if (Step == 7) {
    if (Elapsed < S09ProbeNextAt) return;
    S09ProbeStep = 8;
    return;
  }
  if (Step == 8) {
    // Split verdict: Slate keyboard UX is accepted ONLY when the real Slate
    // event path reached the handlers; the direct InputKey fallback is
    // reported separately and does NOT satisfy the keyboard gate.
    S09KeyRouteArmed = 0;
    const int32 Picks = CommandUi.DiscardSelection.Num();
    const bool bSlate = S09SlateKeySeen > 0;
    const bool bDirect = S09DirectKeySeen > 0;
    const bool bPickApplied = Picks == S09ProbePickCount + 1;
    const TCHAR* Verdict = (bSlate && bPickApplied) ? TEXT("SLATE-PASS")
                               : ((bSlate || bDirect) && bPickApplied)
                                     ? TEXT("SLATE-FAIL-DIRECT-ONLY")
                                     : TEXT("FAIL");
    FS08Trace::Write(FString::Printf(
        TEXT("S09PROBE verdict slate-key-route seen=%d direct-key-route seen=%d picks=%d -> %s"),
        bSlate ? 1 : 0, bDirect ? 1 : 0, Picks, Verdict));
    // ---- scheme-picker scene: quiet action phase, two legal schemes in
    // hand. The manual key route (G opens, 1 selects, Enter confirms,
    // 4 = dead banner rejected, Esc cancels) runs through the SAME Slate
    // event path as the discard probe above.
    CommandUi.DiscardSelection.Reset();
    S09ProbeClearPending(S09ProbeSnapshot);
    S09ProbeSetSchemeHand(S09ProbeSnapshot);
    CommandUi.OnSnapshot(S09ProbeSnapshot, BoardModel, Fighters);
    Hud.Build(S09ProbeSnapshot, S09ProbeHostId, S09ProbePreviousIds,
              S09ProbeSnapshot.SequenceNumber, S09ProbeSnapshot.SequenceNumber);
    SyncBoardFromApplied();
    RefreshHud();
    FS08Trace::Write(TEXT("S09PROBE scheme scene staged (2 legal + 1 non-scheme + 1 dead-banner)"));
    SimulateSlateKeyProbe(EKeys::G, /*bUp=*/false);
    S09ProbeStep = 9;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 9) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::G, /*bUp=*/true);
    S09ProbeStep = 10;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 10) {
    if (Elapsed < S09ProbeNextAt) return;
    const bool bOpen = CommandUi.Mode == ES09CommandMode::SchemeChoice;
    const int32 Playable = bOpen
        ? CommandUi.CountPlayableSchemes(S09ProbeSnapshot, Fighters) : -1;
    FS08Trace::Write(FString::Printf(
        TEXT("S09PROBE scheme picker via slate G: open=%d playable=%d -> %s"),
        bOpen ? 1 : 0, Playable, bOpen && Playable == 2 ? TEXT("PASS") : TEXT("FAIL")));
    TakeEvidenceShot(S09ProbeDir / TEXT("s09-probe-scheme-open.png"));
    SimulateSlateKeyProbe(EKeys::One, /*bUp=*/false);
    S09ProbeStep = 11;
    S09ProbeNextAt = Elapsed + 1.0f;
    return;
  }
  if (Step == 11) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::One, /*bUp=*/true);
    S09ProbeStep = 12;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 12) {
    if (Elapsed < S09ProbeNextAt) return;
    const bool bExact = CommandUi.SchemeCardId == TEXT("sch-any::1");
    FS08Trace::Write(FString::Printf(
        TEXT("S09PROBE scheme pick via slate 1: exact-instance set=%d -> %s"),
        bExact ? 1 : 0, bExact ? TEXT("PASS") : TEXT("FAIL")));
    TakeEvidenceShot(S09ProbeDir / TEXT("s09-probe-scheme-selected.png"));
    SimulateSlateKeyProbe(EKeys::Enter, /*bUp=*/false);
    S09ProbeStep = 13;
    S09ProbeNextAt = Elapsed + 1.0f;
    return;
  }
  if (Step == 13) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::Enter, /*bUp=*/true);
    S09ProbeStep = 14;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 14) {
    if (Elapsed < S09ProbeNextAt) return;
    // Enter confirm: offline probe has no started match, so the transport
    // logs 'SCHEME blocked: match is not started' AFTER the 'SCHEME sent'
    // trace - the confirm route itself is what this step proves. The picker
    // closed and the exact-instance command was issued (never another card).
    const bool bClosed = CommandUi.Mode == ES09CommandMode::None &&
                         CommandUi.SchemeCardId.IsEmpty();
    FS08Trace::Write(FString::Printf(
        TEXT("S09PROBE scheme confirm via Enter: picker closed=%d (offline transport block expected) -> %s"),
        bClosed ? 1 : 0, bClosed ? TEXT("PASS") : TEXT("FAIL")));
    SimulateSlateKeyProbe(EKeys::G, /*bUp=*/false); // reopen for the negatives
    S09ProbeStep = 15;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 15) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::G, /*bUp=*/true);
    S09ProbeStep = 16;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 16) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::Four, /*bUp=*/false); // dead-banner scheme
    S09ProbeStep = 17;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 17) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::Four, /*bUp=*/true);
    S09ProbeStep = 18;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 18) {
    if (Elapsed < S09ProbeNextAt) return;
    const bool bDeadRejected = CommandUi.Mode == ES09CommandMode::SchemeChoice &&
                               CommandUi.SchemeCardId.IsEmpty();
    FS08Trace::Write(FString::Printf(
        TEXT("S09PROBE dead-banner scheme pick: rejected=%d (selection stays empty) -> %s"),
        bDeadRejected ? 1 : 0, bDeadRejected ? TEXT("PASS") : TEXT("FAIL")));
    // Esc stops PIE in the editor before the normal packaged probe reaches
    // its final step. Hold here for MCP pointer inspection of the live HUD.
    if (FParse::Param(FCommandLine::Get(), TEXT("S09McpHold"))) {
      CommandUi.CancelSchemeChoice();
      RefreshHud();
      FS08Trace::Write(TEXT("S09PROBE MCP hold: Slate UI ready for pointer inspection"));
      S09ProbeStep = 21;
      return;
    }
    SimulateSlateKeyProbe(EKeys::Escape, /*bUp=*/false);
    S09ProbeStep = 19;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 19) {
    if (Elapsed < S09ProbeNextAt) return;
    SimulateSlateKeyProbe(EKeys::Escape, /*bUp=*/true);
    S09ProbeStep = 20;
    S09ProbeNextAt = Elapsed + 0.5f;
    return;
  }
  if (Step == 20) {
    if (Elapsed < S09ProbeNextAt) return;
    const bool bCancelled = CommandUi.Mode == ES09CommandMode::None;
    FS08Trace::Write(FString::Printf(
        TEXT("S09PROBE scheme cancel via Esc: picker closed=%d -> %s"),
        bCancelled ? 1 : 0, bCancelled ? TEXT("PASS") : TEXT("FAIL")));
    FS08Trace::Write(
        TEXT("S09PROBE mouse-click path: MANUAL-OPEN (no real cursor hit-test in the packaged probe)"));
    FS08Trace::Close();
    FGenericPlatformMisc::RequestExit(false);
  }
}

// ---- demo drive ----------------------------------------------------------

void AS08FlowGameMode::RunAutoManeuver() {
  if (!Flow.IsValid() || !BoardActor) return;
  // S10/GD-040: never attempt a maneuver in an interrupted room - the gate
  // would reject it every poll tick (blocked-trace spam in the live run).
  if (Flow->IsRoomAborted()) return;
  // Pick the own hero; move one step to a legal board neighbour (a linked
  // space on an original map, orthogonal +X/-X/+Y/-Y on a grid).
  const FS08BoardFighter* Hero = nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.OwnerId == Flow->GetUserId() && Entry.bIsHero && Entry.IsAlive()) {
      Hero = &Entry;
      break;
    }
  }
  if (!Hero) return;
  const TSet<uint64> Reachable = FS08BoardModel::ComputeReachableCells(
      BoardModel, Fighters, Hero->Id, Hero->Movement);
  int32 TargetX = -1, TargetY = -1;
  for (const FIntPoint& Next : BoardModel.Neighbours(FIntPoint(Hero->X, Hero->Y))) {
    if (Reachable.Contains(FS08BoardModel::CellKey(Next.X, Next.Y))) {
      TargetX = Next.X;
      TargetY = Next.Y;
      break;
    }
  }
  if (TargetX < 0) return;
  SelectFighter(Hero->Id);
  Toast = FString::Printf(TEXT("AUTO maneuver: %s [%s] (%d,%d)->(%d,%d)"), *Hero->Label,
                          *Hero->Id, Hero->X, Hero->Y, TargetX, TargetY);
  ToastUntil = Elapsed + 5.0f;
  bAutoManeuverDone = true; // one shot only; WS/HTTP dedupe proven by traces
  ManeuverStartSeq = Flow->GetAppliedSnapshot().SequenceNumber;
  TryManeuverTo(TargetX, TargetY);
}

void AS08FlowGameMode::TakeEvidenceShot(const FString& InPath) {
  auto* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC) return;
  bShotTaken = true;
  // Diagnostics: what the renderer actually sees at this moment.
  {
    FVector2D ViewportSize(0.0, 0.0);
    if (GEngine && GEngine->GameViewport) {
      GEngine->GameViewport->GetViewportSize(ViewportSize);
    }
    const FVector CamLoc = PC->PlayerCameraManager
                               ? PC->PlayerCameraManager->GetCameraLocation()
                               : FVector::ZeroVector;
    const FRotator CamRot = PC->PlayerCameraManager
                                ? PC->PlayerCameraManager->GetCameraRotation()
                                : FRotator::ZeroRotator;
    const AActor* VT = PC->GetViewTarget();
    FS08Trace::Write(FString::Printf(
        TEXT("SHOT ctx viewport=%dx%d viewTarget=%s cam=(%.0f,%.0f,%.0f) rot=(%.0f,%.0f,%.0f)"),
        static_cast<int32>(ViewportSize.X), static_cast<int32>(ViewportSize.Y),
        VT ? *VT->GetName() : TEXT("none"), CamLoc.X, CamLoc.Y, CamLoc.Z,
        CamRot.Pitch, CamRot.Yaw, CamRot.Roll));
    // W4-A RENDER fingerprint of THIS frame (RHI, SM, GI/reflections, sg.*,
    // screen percentage, AA, exposure, light units, t.MaxFPS/VSync, profile
    // sha). classify_evidence / qa010 reject frames without it or off the
    // reference (docs/art-pipeline/render-reference.json).
    FS08Trace::Write(S08RenderFingerprint(
        GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(), TEXT("SHOT")));
    // GD-030 diagnosis: every fighter's projected screen position at shot
    // time - answers "in frame or not" without eyeballing the PNG.
    if (BoardActor) {
      for (const FS08BoardFighter& F : Fighters) {
        const FVector World = BoardModel.CellToWorld(F.X, F.Y);
        FVector2D Screen(0, 0);
        const bool bProjected = PC->ProjectWorldLocationToScreen(World, Screen, true);
        FS08Trace::Write(FString::Printf(
            TEXT("SHOT fighter %s pos=(%d,%d) world=(%.0f,%.0f,%.0f) screen=(%.0f,%.0f) projected=%d alive=%d"),
            *F.Id, F.X, F.Y, World.X, World.Y, World.Z, Screen.X, Screen.Y,
            bProjected ? 1 : 0, F.IsAlive() ? 1 : 0));
      }
    }
    // ART-004 T1.1: camera state and the Head-socket projection of every
    // visible skeletal art figure, so K2 crops are reproducible from the
    // trace (crop centre = Head, head height = |proj(Head+6uu) - proj(Head-6uu)|).
    if (BoardActor && BoardActor->IsArtActive()) {
      const float DistErrPct = CameraZoom.Target > 0.0f
          ? 100.0f * FMath::Abs(CameraZoom.Current - CameraZoom.Target) / CameraZoom.Target
          : -1.0f;
      const float FocusErr = FVector::Dist(CameraZoom.CurrentFocus, CameraZoom.TargetFocus);
      FS08Trace::Write(FString::Printf(
          TEXT("SHOT camera dist=%.1f target=%.1f overview=%.1f errPct=%.3f focusErr=%.2f settled=%d zoom=%.2f"),
          CameraZoom.Current, CameraZoom.Target, CameraZoom.Overview, DistErrPct,
          FocusErr, (DistErrPct >= 0.0f && DistErrPct < 1.0f && FocusErr < 1.0f) ? 1 : 0,
          CameraZoom.ZoomOf(CameraZoom.Current)));
      for (const FS08BoardFighter& F : Fighters) {
        const AS08FighterActor* Actor = BoardActor->FindFighterActor(F.Id);
        const USkeletalMeshComponent* Skel =
            Actor ? Actor->FindComponentByClass<USkeletalMeshComponent>() : nullptr;
        if (!Skel || !Skel->IsVisible() || !Skel->GetSkeletalMeshAsset() ||
            !Skel->DoesSocketExist(TEXT("Head"))) {
          continue;
        }
        const FVector Head = Skel->GetSocketLocation(TEXT("Head"));
        FVector2D HeadScreen(0, 0), TopScreen(0, 0), BottomScreen(0, 0);
        const bool bHead = PC->ProjectWorldLocationToScreen(Head, HeadScreen, true);
        const bool bTop = PC->ProjectWorldLocationToScreen(Head + FVector(0, 0, 6), TopScreen, true);
        const bool bBottom =
            PC->ProjectWorldLocationToScreen(Head - FVector(0, 0, 6), BottomScreen, true);
        FS08Trace::Write(FString::Printf(
            TEXT("SHOT head fighter=%s socket=Head mesh=%s world=(%.1f,%.1f,%.1f) screen=(%.1f,%.1f) top=(%.1f,%.1f) bottom=(%.1f,%.1f) headPx=%.1f projected=%d"),
            *F.Id, *Skel->GetSkeletalMeshAsset()->GetName(), Head.X, Head.Y, Head.Z,
            HeadScreen.X, HeadScreen.Y, TopScreen.X, TopScreen.Y, BottomScreen.X, BottomScreen.Y,
            FVector2D::Distance(TopScreen, BottomScreen), (bHead && bTop && bBottom) ? 1 : 0));
      }
    }
    // ART-004 T2.2 / QA-010: selection, reachable and plate boxes of THIS frame in viewport pixels (format:
    // docs/art-pipeline/qa010/README.md "Новая трасса"). W5b-R: the icon / widget / tag / damage lines moved to the
    // END of this frame (WriteArtHudLateLines) - they report what the capture really contains.
    WriteArtHudShotLines();
  }
  // UI-INCLUSIVE evidence capture (GD-032/033): the old SceneCapture and
  // HighResShot paths render the 3D scene only - Slate HUD widgets never
  // reach those pixels, so published shots silently proved nothing about the
  // HUD. FScreenshotRequest::RequestScreenshot(path, bShowUI=true, false)
  // composites the viewport + Slate UI (UE 5.8 UnrealClient.h). "slate" mode
  // renders the HUD canvas widget alone through the Slate renderer for the
  // offscreen fallback probe.
  const FString BasePath = InPath.IsEmpty() ? AutoShotPath : InPath;
  if (BasePath.IsEmpty()) return;
  if (S09ShotMode == TEXT("slate") && HudCanvas.IsValid()) {
    TArray<FColor> Pixels;
    FIntVector Size(0, 0, 0);
    if (FSlateApplication::Get().TakeScreenshot(HudCanvas.ToSharedRef(), Pixels, Size) &&
        Size.X > 0 && Size.Y > 0) {
      TArray64<uint8> Png;
      FImageUtils::PNGCompressImageArray(Size.X, Size.Y, Pixels, Png);
      if (FFileHelper::SaveArrayToFile(Png, *BasePath)) {
        const FString Line =
            FString::Printf(TEXT("SHOT saved: slate widget %dx%d -> %s"), Size.X, Size.Y, *BasePath);
        TraceLines.Add(Line);
        FS08Trace::Write(Line);
        return;
      }
    }
    FS08Trace::Write(TEXT("SHOT slate widget capture FAILED"));
  } else {
    FScreenshotRequest::RequestScreenshot(BasePath, /*bShowUI=*/true,
                                          /*bAddFilenameSuffix=*/false);
    // W5b-R: HandleScreenshotCaptured saves exactly this path; the late SHOT lines run at the end of this frame.
    ArtHud.PendingCapturePath = BasePath;
    ArtHud.PendingCaptureRequestFrame = GFrameCounter;
    ArtHud.LateShots.Add({FPaths::GetCleanFilename(BasePath), GFrameCounter});
    FS08Trace::Write(FString::Printf(TEXT("SHOT request file=%s frame=%llu"), *FPaths::GetCleanFilename(BasePath),
                                     static_cast<unsigned long long>(GFrameCounter)));
    const FString Line =
        FString::Printf(TEXT("SHOT requested: FScreenshotRequest(bShowUI) -> %s"), *BasePath);
    TraceLines.Add(Line);
    FS08Trace::Write(Line);
  }
}

void AS08FlowGameMode::Tick(float DeltaSeconds) {
  Super::Tick(DeltaSeconds);
  Elapsed += DeltaSeconds;
  PollAccumulator += DeltaSeconds;
  // ART-004 T1.1 opt-in frame timing (-S08Perf). FApp::GetDeltaTime() is the
  // real frame interval (it includes the t.MaxFPS wait), so fps is the
  // effective rate; GPU/game/render thread times are the same engine globals
  // the CSV profiler records (GPUTime, GameThreadTime, RenderThreadTime).
  if (!GS08ArtProbe.bPerfInit) {
    GS08ArtProbe.bPerfInit = true;
    GS08ArtProbe.bPerf = FParse::Param(FCommandLine::Get(), TEXT("S08Perf"));
    GS08ArtProbe.WindowStart = Elapsed;
  }
  if (GS08ArtProbe.bPerf) {
    const float FrameMs = static_cast<float>(FApp::GetDeltaTime() * 1000.0);
    const float GpuMs = static_cast<float>(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles()));
    const float GameMs = static_cast<float>(FPlatformTime::ToMilliseconds(GGameThreadTime));
    const float RenderMs = static_cast<float>(FPlatformTime::ToMilliseconds(GRenderThreadTime));
    GS08ArtProbe.WindowFrameMs.Add(FrameMs);
    GS08ArtProbe.WindowGpuMs.Add(GpuMs);
    GS08ArtProbe.WindowGameMs.Add(GameMs);
    GS08ArtProbe.WindowRenderMs.Add(RenderMs);
    if (Elapsed >= GS08PerfWarmupSeconds) {
      GS08ArtProbe.RunFrameMs.Add(FrameMs);
      GS08ArtProbe.RunGpuMs.Add(GpuMs);
      GS08ArtProbe.RunGameMs.Add(GameMs);
      GS08ArtProbe.RunRenderMs.Add(RenderMs);
    }
    if (Flow.IsValid() && Flow->GetStage() == ES08Stage::Started) {
      GS08ArtProbe.StartedFrameMs.Add(FrameMs);
      GS08ArtProbe.StartedGpuMs.Add(GpuMs);
      GS08ArtProbe.StartedGameMs.Add(GameMs);
      GS08ArtProbe.StartedRenderMs.Add(RenderMs);
    }
    if (ArtHud.bPlateVisible) {
      GS08ArtProbe.ArtHudFrameMs.Add(FrameMs);
      GS08ArtProbe.ArtHudGpuMs.Add(GpuMs);
      GS08ArtProbe.ArtHudGameMs.Add(GameMs);
      GS08ArtProbe.ArtHudRenderMs.Add(RenderMs);
      // Alternate: steady frames only (a swap re-lays out the shown pair).
      if (static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate && ArtHud.bAlternateStarted &&
          ArtHud.FramesSinceSwap > 5 && ArtHud.PlateViews.IsValidIndex(ArtHud.ActiveView)) {
        const int32 I = FCString::Strcmp(ArtHud.PlateViews[ArtHud.ActiveView]->ImplName(), TEXT("umg")) == 0 ? 0 : 1;
        GS08ArtProbe.AltFrameMs[I].Add(FrameMs);
        GS08ArtProbe.AltGpuMs[I].Add(GpuMs);
        GS08ArtProbe.AltGameMs[I].Add(GameMs);
        GS08ArtProbe.AltRenderMs[I].Add(RenderMs);
        GS08ArtProbe.PeriodGameMs.Add(GameMs);
        GS08ArtProbe.PeriodGpuMs.Add(GpuMs);
      }
    }
    if (Elapsed - GS08ArtProbe.WindowStart >= GS08PerfWindowSeconds) {
      if (!GS08ArtProbe.bPerfConfigLogged) {
        GS08ArtProbe.bPerfConfigLogged = true;
        S08WritePerfConfig();
        FS08Trace::Write(S08RenderFingerprint(
            GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(), TEXT("PERF")));
      }
      FS08Trace::Write(FString::Printf(
          TEXT("PERF window t=%.1f-%.1f %s"), GS08ArtProbe.WindowStart, Elapsed,
          *S08PerfStats(GS08ArtProbe.WindowFrameMs, GS08ArtProbe.WindowGpuMs,
                        GS08ArtProbe.WindowGameMs, GS08ArtProbe.WindowRenderMs)));
      GS08ArtProbe.WindowStart = Elapsed;
      GS08ArtProbe.WindowFrameMs.Reset();
      GS08ArtProbe.WindowGpuMs.Reset();
      GS08ArtProbe.WindowGameMs.Reset();
      GS08ArtProbe.WindowRenderMs.Reset();
    }
  }
  if (Flow.IsValid()) {
    // GD-028 recovery: bounded-backoff WS reconnect (idle when attached).
    Flow->TickConnectivity(DeltaSeconds);
    // Test hook: abrupt transport loss after the stream is live.
    if (AutoDropWsAfter > 0.0f && !bWsDroppedForTest && Flow->IsStreamAttached() &&
        Elapsed >= AutoDropWsAfter) {
      bWsDroppedForTest = true;
      Flow->DropWsForTest();
    }
    // Lobby freshness without named-subscription barrier: re-query game(id).
    if (PollAccumulator >= 3.0f) {
      PollAccumulator = 0.0f;
      if (Flow->WantsPolling()) Flow->PollRoom();
      AutoAdvance();
    }
    // Second leg of the click/auto maneuver: beginManeuver drew a card and
    // opened pendingManeuver; complete it with the remembered destination.
    if (bAwaitManeuverFinish) {
      const FString PendingId = FS08Contracts::PendingManeuverId(Flow->GetAppliedSnapshot());
      if (!PendingId.IsEmpty()) {
        bAwaitManeuverFinish = false;
        FinishPendingManeuver(ManeuverTargetX, ManeuverTargetY);
      }
    }
  }
  HandleClick();
  HandleHudKeys();
  // Sync the in-flight gate every tick, not only on applied snapshots: a
  // mutation-reply (e.g. a rejected endTurn) can clear Flow's flag AFTER the
  // last apply, and the stale CommandUi copy would block the next command
  // until an unrelated snapshot arrives (stuck auto-decline in the S09 demo).
  if (Flow.IsValid()) CommandUi.bCommandInFlight = Flow->IsManeuverInFlight();
  TakeS09Shots();
  RunS09Auto();
  RunS10AbortProof();
  if (bS09Probe) RunS09HudProbe();
  if (bBench) RunRenderBench();
  // GD-034: the server deadline countdown must tick without a new snapshot.
  if (CommandUi.Mode == ES09CommandMode::CombatDefense ||
      CommandUi.Mode == ES09CommandMode::CombatResolve) {
    HudTickAccumulator += DeltaSeconds;
    if (HudTickAccumulator >= 0.25f) {
      HudTickAccumulator = 0.0f;
      RefreshHud();
    }
  }
  if (ToastUntil > 0.0f && Elapsed > ToastUntil) {
    ToastUntil = 0.0f;
    Toast.Reset();
    RefreshUi();
  }
  if (IllegalUntil > 0.0f && Elapsed > IllegalUntil) {
    IllegalUntil = 0.0f;
    if (BoardActor) BoardActor->HideIllegalCell();
  }
  // An opt-in visual probe uses the same local selection path as a click,
  // without sending a gameplay mutation. The packaged screenshot then shows
  // the authored selection-ring mesh against the live board and HUD.
  if (bArtPreviewSelectOwnHero && !bArtPreviewDidSelectOwnHero &&
      ArtPreviewShotAfter >= 2.0f && Elapsed >= ArtPreviewShotAfter - 2.0f &&
      BoardActor && BoardActor->IsArtActive() && Flow.IsValid() &&
      Flow->GetStage() == ES08Stage::Started) {
    for (const FS08BoardFighter& Entry : Fighters) {
      if (Entry.OwnerId == Flow->GetUserId() && Entry.bIsHero && Entry.IsAlive()) {
        SelectFighter(Entry.Id);
        bArtPreviewDidSelectOwnHero = true;
        FS08Trace::Write(FString::Printf(
            TEXT("ARTPREVIEW selection ownHero=1 selected=%d fighter=%s reachable=%d fighterId=%s"),
            SelectedFighterId == Entry.Id ? 1 : 0, *Entry.Name,
            ReachableCells.Num(), *Entry.Id));
        // The flag selection is input emulation, not a user click (E4).
        FS08Trace::Write(FString::Printf(TEXT("INPUT select src=flag fighter=%s flag=ArtPreviewSelectOwnHero"),
                                         *Entry.Id));
        if (ArtPreviewFocusZoom > 0.0f && CameraZoom.IsReady()) {
          const FS08ZoomStep Step = CameraZoom.FocusZoom(ArtPreviewFocusZoom);
          FS08Trace::Write(FString::Printf(
              TEXT("ARTPREVIEW camera focus requested zoom=%.2f overview=%.0f target=%.0f"),
              ArtPreviewFocusZoom, CameraZoom.Overview, CameraZoom.Target));
          FS08Trace::Write(FString::Printf(TEXT("INPUT zoom src=flag zoom=%.2f flag=ArtPreviewFocusZoom"),
                                           ArtPreviewFocusZoom));
          FS08Trace::Write(FString::Printf(
              TEXT("CAMERA focus src=flag from=%.1f to=%.1f requested=%.1f zoom=%.2f clamp=%d limit=%s animMs=%.0f"),
              Step.From, Step.To, Step.Requested, CameraZoom.ZoomOf(Step.To), Step.bClamped ? 1 : 0,
              S08ZoomLimitName(Step.Limit), Step.Seconds * 1000.0f));
          if (Step.bClamped) {
            FS08Trace::Write(FString::Printf(
                TEXT("CAMERA clamp limit=%s src=flag dist=%.1f requested=%.1f zoom=%.2f"),
                S08ZoomLimitName(Step.Limit), Step.To, Step.Requested, CameraZoom.ZoomOf(Step.To)));
          }
        }
        break;
      }
    }
  }
  UpdateBoardCamera(DeltaSeconds);
  UpdateArtHud(DeltaSeconds);
  // ART-004 T1.1 K2 gate: log once when the requested focus zoom has arrived
  // (|distance - target| < 1 % of the target and the focus point within 1 uu).
  if (bArtPreviewDidSelectOwnHero && ArtPreviewFocusZoom > 0.0f &&
      !GS08ArtProbe.bCameraSettledLogged && CameraZoom.Target > 0.0f) {
    const float DistErrPct = 100.0f * FMath::Abs(CameraZoom.Current - CameraZoom.Target) /
                             CameraZoom.Target;
    const float FocusErr = FVector::Dist(CameraZoom.CurrentFocus, CameraZoom.TargetFocus);
    if (DistErrPct < 1.0f && FocusErr < 1.0f) {
      GS08ArtProbe.bCameraSettledLogged = true;
      FS08Trace::Write(FString::Printf(
          TEXT("CAMERA settled elapsed=%.2f dist=%.1f target=%.1f errPct=%.3f focusErr=%.2f focus=(%.0f,%.0f,%.0f)"),
          Elapsed, CameraZoom.Current, CameraZoom.Target, DistErrPct, FocusErr,
          CameraZoom.CurrentFocus.X, CameraZoom.CurrentFocus.Y, CameraZoom.CurrentFocus.Z));
    }
  }
  // Cobble's opening six figures can occupy every orthogonal square around
  // Medusa. Capture the authoritative, HUD-inclusive settled board even when
  // the historical one-step S08 demo has no legal move on this map.
  if (!bShotTaken && ArtPreviewShotAfter >= 0.0f && Elapsed >= ArtPreviewShotAfter &&
      !AutoShotPath.IsEmpty() && BoardActor && BoardActor->IsArtActive() &&
      Flow.IsValid() && Flow->GetStage() == ES08Stage::Started &&
      Flow->GetAppliedSnapshot().SequenceNumber > 0) {
    TakeEvidenceShot(FString());
  }
  if (!bShotTaken && Flow.IsValid() && !Flow->IsManeuverInFlight()) {
    // Host path: maneuver complete = begin (seq+1) and submit (seq+2) both
    // applied, pending cleared. Joiner path: an authoritative cue arrived
    // (it saw the same event over the stream). Give the renderer a beat
    // before the evidence shot.
    const FS08Snapshot& Snap = Flow->GetAppliedSnapshot();
    const bool ManeuverSettled =
        bAutoManeuver && bAutoManeuverDone &&
        Snap.SequenceNumber >= ManeuverStartSeq + 2 &&
        FS08Contracts::PendingManeuverId(Snap).IsEmpty();
    const bool CueSeen = !bAutoManeuver && bSawCue;
    if (ShotAtElapsed < 0.0f && (ManeuverSettled || CueSeen)) {
      ShotAtElapsed = Elapsed + 1.5f;
    }
    if (ShotAtElapsed >= 0.0f && Elapsed >= ShotAtElapsed) {
      TakeEvidenceShot(FString());
    }
  }
  if (AutoExitAfter > 0.0f && Elapsed > AutoExitAfter) {
    UE_LOG(LogTemp, Display, TEXT("S08_FLOW_COMPLETE elapsed=%f"), Elapsed);
    if (GS08ArtProbe.bPerf && !GS08ArtProbe.bPerfSummaryLogged) {
      GS08ArtProbe.bPerfSummaryLogged = true;
      if (!GS08ArtProbe.bPerfConfigLogged) {
        S08WritePerfConfig();
        FS08Trace::Write(S08RenderFingerprint(
            GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(), TEXT("PERF")));
      }
      FS08Trace::Write(FString::Printf(
          TEXT("PERF summary scope=afterWarmup warmup=%.0f elapsed=%.1f %s"),
          GS08PerfWarmupSeconds, Elapsed,
          *S08PerfStats(GS08ArtProbe.RunFrameMs, GS08ArtProbe.RunGpuMs,
                        GS08ArtProbe.RunGameMs, GS08ArtProbe.RunRenderMs)));
      FS08Trace::Write(FString::Printf(
          TEXT("PERF summary scope=started elapsed=%.1f %s"), Elapsed,
          *S08PerfStats(GS08ArtProbe.StartedFrameMs, GS08ArtProbe.StartedGpuMs,
                        GS08ArtProbe.StartedGameMs, GS08ArtProbe.StartedRenderMs)));
      // W4-C: frames with the art HUD plate on screen, per implementation.
      FS08Trace::Write(FString::Printf(
          TEXT("PERF summary scope=artHud impl=%s elapsed=%.1f %s"),
          S08ArtHudImplName(static_cast<ES08ArtHudImpl>(ArtHud.Impl)), Elapsed,
          *S08PerfStats(GS08ArtProbe.ArtHudFrameMs, GS08ArtProbe.ArtHudGpuMs,
                        GS08ArtProbe.ArtHudGameMs, GS08ArtProbe.ArtHudRenderMs)));
      if (static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate) {
        for (int32 I = 0; I < 2; ++I) {
          FS08Trace::Write(FString::Printf(
              TEXT("PERF summary scope=%s impl=%s swaps=%d periodS=%.1f elapsed=%.1f %s gameP50=%.3f gameP99=%.3f"),
              I == 0 ? TEXT("artHudUmg") : TEXT("artHudSlate"), I == 0 ? TEXT("umg") : TEXT("slate"), ArtHud.Swaps,
              ArtHud.AlternateSeconds, Elapsed,
              *S08PerfStats(GS08ArtProbe.AltFrameMs[I], GS08ArtProbe.AltGpuMs[I], GS08ArtProbe.AltGameMs[I],
                            GS08ArtProbe.AltRenderMs[I]),
              S08PerfPercentile(GS08ArtProbe.AltGameMs[I], 0.50f), S08PerfPercentile(GS08ArtProbe.AltGameMs[I], 0.99f)));
        }
      }
    }
    FS08Trace::Close();
    FGenericPlatformMisc::RequestExit(false);
  }
}

void AS08FlowGameMode::EndPlay(const EEndPlayReason::Type Reason) {
  FCoreDelegates::OnEndFrame.Remove(EndFrameHandle);
  UGameViewportClient::OnScreenshotCaptured().Remove(ScreenshotCapturedHandle);
  FS08Trace::Close();
  if (Flow.IsValid()) Flow.Reset();
  Super::EndPlay(Reason);
}

void AS08FlowGameMode::BuildUi() {
  if (!GEngine || !GEngine->GameViewport) return;

  TSharedRef<SVerticalBox> Root = SNew(SVerticalBox);
  Root->AddSlot().AutoHeight()
      [SNew(STextBlock).Text(FText::FromString(TEXT("UNMATCHED S08 grey flow (GD-028..031)")))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))];

  Root->AddSlot().AutoHeight()[SNew(SSeparator)];
  Root->AddSlot().AutoHeight()[SAssignNew(StatusLine, STextBlock)];

  // LOGIN. SAssignNew cannot be used inside a slotted `+ Slot()[...]` chain
  // (parser limitation), so the editable boxes are created up front and
  // exposed to the weak members by hand.
  TSharedRef<SEditableTextBox> EmailRef = SNew(SEditableTextBox);
  EmailBox = EmailRef;
  Root->AddSlot().AutoHeight()
      .Padding(4)[SNew(SHorizontalBox) +
                  SHorizontalBox::Slot().AutoWidth()
                      [SNew(STextBlock).Text(FText::FromString(TEXT("email: ")))] +
                  SHorizontalBox::Slot().FillWidth(0.4f)[EmailRef]];
  TSharedRef<SEditableTextBox> PasswordRef = SNew(SEditableTextBox).IsPassword(true);
  PasswordBox = PasswordRef;
  Root->AddSlot().AutoHeight()
      .Padding(4)[SNew(SHorizontalBox) +
                  SHorizontalBox::Slot().AutoWidth()
                      [SNew(STextBlock).Text(FText::FromString(TEXT("password: ")))] +
                  SHorizontalBox::Slot().FillWidth(0.4f)[PasswordRef]];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("LOGIN")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid() && EmailBox.IsValid() && PasswordBox.IsValid()) {
               Flow->Login(EmailBox.Pin()->GetText().ToString(),
                           PasswordBox.Pin()->GetText().ToString());
             }
             return FReply::Handled();
           })];

  Root->AddSlot().AutoHeight()[SNew(SSeparator)];
  // LOBBY
  // Room entry stays dead while a match is live (Stage Started, incl. the
  // F10 operator overlay): replacing the room without an accepted LeaveRoom
  // would strand the old WS subscription. LEAVE ROOM is the only live exit.
  // S10/GD-039: visible mode control - ONE_V_ONE (human pair) vs VS_AI (the
  // server bot takes the second seat on startGame).
  {
    TSharedRef<SHorizontalBox> ModeRow = SNew(SHorizontalBox);
    ModeRow->AddSlot().AutoWidth().Padding(0, 0, 8, 0)
        [SNew(STextBlock).Text(FText::FromString(TEXT("mode:")))];
    ModeRow->AddSlot().AutoWidth().Padding(0, 0, 10, 0)
        [SNew(SCheckBox)
             .IsChecked_Lambda([this]() {
               return LobbyCreateMode == TEXT("ONE_V_ONE") ? ECheckBoxState::Checked
                                                           : ECheckBoxState::Unchecked;
             })
             .OnCheckStateChanged_Lambda([this](ECheckBoxState) {
               LobbyCreateMode = TEXT("ONE_V_ONE");
               RefreshUi();
             })
             .Content()[SNew(STextBlock).Text(FText::FromString(TEXT("ONE_V_ONE")))]];
    ModeRow->AddSlot().AutoWidth()
        [SNew(SCheckBox)
             .IsChecked_Lambda([this]() {
               return LobbyCreateMode == TEXT("VS_AI") ? ECheckBoxState::Checked
                                                       : ECheckBoxState::Unchecked;
             })
             .OnCheckStateChanged_Lambda([this](ECheckBoxState) {
               LobbyCreateMode = TEXT("VS_AI");
               RefreshUi();
             })
             .Content()[SNew(STextBlock).Text(FText::FromString(TEXT("VS_AI (bot)")))]];
    ModeRow->AddSlot().AutoWidth().Padding(10, 0, 0, 0)
        [SNew(STextBlock)
             .Text_Lambda([this]() {
               return FText::FromString(LobbyCreateMode == TEXT("VS_AI")
                                            ? FString(TEXT(
                                                  "VS_AI: you start alone - the server bot joins on start"))
                                            : FString());
             })];
    Root->AddSlot().AutoHeight().Padding(4)[ModeRow];
  }
  {
    TSharedRef<SHorizontalBox> CreateRow = SNew(SHorizontalBox);
    CreateRow->AddSlot().AutoWidth()
        [SNew(SButton).Text(FText::FromString(TEXT("CREATE ROOM")))
             .IsEnabled_Lambda([this]() {
               return !Flow.IsValid() || Flow->GetStage() != ES08Stage::Started;
             })
             .OnClicked_Lambda([this]() {
               if (Flow.IsValid()) Flow->CreateRoom(LobbyCreateMode);
               return FReply::Handled();
             })];
    CreateRow->AddSlot().AutoWidth().Padding(10, 2, 0, 0)
        [SNew(STextBlock)
             .Text_Lambda([this]() {
               return FText::FromString(TEXT("creates: ") + LobbyCreateMode);
             })];
    Root->AddSlot().AutoHeight().Padding(4)[CreateRow];
  }
  TSharedRef<SEditableTextBox> CodeRef = SNew(SEditableTextBox);
  CodeBox = CodeRef;
  Root->AddSlot().AutoHeight()
      .Padding(4)[SNew(SHorizontalBox) +
                  SHorizontalBox::Slot().AutoWidth()
                      [SNew(STextBlock).Text(FText::FromString(TEXT("room code: ")))] +
                  SHorizontalBox::Slot().FillWidth(0.2f)[CodeRef]];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("JOIN BY CODE")))
           .IsEnabled_Lambda([this]() {
             return !Flow.IsValid() || Flow->GetStage() != ES08Stage::Started;
           })
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid() && CodeBox.IsValid()) {
               Flow->JoinRoomByCode(CodeBox.Pin()->GetText().ToString().TrimStartAndEnd());
             }
             return FReply::Handled();
           })];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("RECOVER MY ROOM (myGames)")))
           .IsEnabled_Lambda([this]() {
             return !Flow.IsValid() || Flow->GetStage() != ES08Stage::Started;
           })
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->EnterLobby();
             return FReply::Handled();
           })];

  Root->AddSlot().AutoHeight()[SNew(SSeparator)];
  // ROOM
  Root->AddSlot().AutoHeight()[SAssignNew(RoomLine, STextBlock)];
  Root->AddSlot().AutoHeight()[SAssignNew(PlayersLine, STextBlock)];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("TOGGLE READY")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->ToggleReady();
             return FReply::Handled();
           })];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("START GAME (host)")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->StartGame();
             return FReply::Handled();
           })];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("LEAVE ROOM")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->LeaveRoom();
             return FReply::Handled();
           })];

  Root->AddSlot().AutoHeight()[SNew(SSeparator)];
  // BOARD (GD-030) + command gate (GD-031)
  Root->AddSlot().AutoHeight()[SAssignNew(BoardLine, STextBlock)];
  Root->AddSlot().AutoHeight()[SAssignNew(ToastLine, STextBlock)];
  Root->AddSlot().AutoHeight()[SAssignNew(ProblemLine, STextBlock)];
  // Trace
  Root->AddSlot().FillHeight(1.0f)
      [SNew(SScrollBox) + SScrollBox::Slot()[SAssignNew(TraceBox, SVerticalBox)]];

  LegacyRoot = Root;
  GEngine->GameViewport->AddViewportWidgetContent(Root, 0);
  UpdateLegacyRootVisibility();
  BuildHudWidgets();
}

void AS08FlowGameMode::UpdateLegacyRootVisibility() {
  if (!LegacyRoot.IsValid()) return;
  // Gameplay (and the backend-less probe) must not show the legacy panel:
  // it carries the joinable room code and the full trace log, and it used to
  // stretch across the whole viewport over the board. The post-duel Lobby
  // shows the user-facing HUD lobby panel instead; the legacy form stays an
  // F10 operator overlay there too. Login (pre-auth) and Room keep it.
  const bool bGameplay =
      bS09Probe || bBench || (Flow.IsValid() &&
                    (Flow->GetStage() == ES08Stage::Started ||
                     Flow->GetStage() == ES08Stage::Lobby));
  const bool bVisible = !bGameplay || bDebugPanelForced;
  LegacyRoot->SetVisibility(bVisible ? EVisibility::Visible : EVisibility::Collapsed);
}

void AS08FlowGameMode::OnStageChanged(ES08Stage OldStage, ES08Stage NewStage) {
  // Entering Started: a fresh match must not inherit the previous duel's
  // result-drive state (the RESULT trace dedupe would swallow the new game's
  // first matching seq, and a spent leave/shot flags pair would skip the
  // result tail entirely).
  if (NewStage == ES08Stage::Started) {
    ResultPanelBuiltAtElapsed = -1.0f;
    S09ResultTraceSeq = -1;
    bS09LobbyReturnSent = false;
    bS09AutoLeaveRetryBlocked = false;
    bS09ShotResultScreen = false;
    S09ShotResultScreenPath.Reset();
    ShotResultScreenAtElapsed = -1.0f;
    bS09ShotLobby = false;
    S09ShotLobbyPath.Reset();
    ShotLobbyAtElapsed = -1.0f;
    LobbyShotNotBeforeElapsed = -1.0f;
    bS09DuelComplete = false;
    return;
  }
  // Leaving Started: tear the runtime board down. The 11:47 lobby shots
  // showed the stale 5x6 board + fighter labels behind the lobby form - a
  // finished duel must not leak in-game artifacts into the Lobby.
  if (BoardActor) {
    BoardActor->Destroy();
    BoardActor = nullptr;
  }
  // BoardCamera stays: the view target keeps pointing at it (destroying a
  // live view target would blank the frame); the empty arena behind the
  // lobby panel is the intended neutral backdrop.
  Fighters.Reset();
  BoardModel = FS08BoardModel();
  SelectedFighterId.Reset();
  ReachableCells.Reset();
  // The gameplay HUD must go with it - on EVERY exit path (manual leaveGame
  // reply AND the S09AUTO tail), not only the auto-driven result flow: the
  // model still holds the terminal snapshot (bGameOver) and would keep the
  // result panel rendering OVER the lobby screen.
  if (OldStage == ES08Stage::Started) {
    ClearGameplayHud();
  }
}

void AS08FlowGameMode::ClearGameplayHud() {
  Hud = FS09HudModel();
  CommandUi = FS09CommandUi();
  if (Flow.IsValid()) CommandUi.ViewerId = Flow->GetUserId();
  LastCombatResult = FS09CombatResult();
  PrevApplied = FS08Snapshot();
  bHasPrevApplied = false;
  CombatStartTargetId.Reset();
  CombatStartTargetHealth = -1;
  bS09ShotDamage = false;
  DamageShotAtElapsed = -1.0f;
  PreviousOwnHandIds.Reset();
  PreviousHandSeq = 0;
  bDiscardBrowserOpen = false;
  DiscardBrowserPile = 0;
  DiscardBrowserIndex = -1;
  InspectedSource = 0;
  bInspecting = false;
  InspectedHandIndex = -1;
  bAwaitManeuverFinish = false;
  ManeuverTargetX = -1;
  ManeuverTargetY = -1;
  RefreshHud();
  FS08Trace::Write(TEXT("GAMEPLAY HUD cleared (left Started)"));
}

// ---- GD-032/033 HUD overlay ----------------------------------------------

void AS08FlowGameMode::BuildHudWidgets() {
  if (!GEngine || !GEngine->GameViewport) return;
  TSharedRef<SConstraintCanvas> Canvas = SNew(SConstraintCanvas);
  HudCanvas = Canvas;
  // ART-004 T2.2 world-anchored layer first: the plate and the combat icon
  // paint below the HUD panels (they are placed around them anyway).
  BuildArtHudWidgets(Canvas);
  TSharedPtr<SBorder> CommandPanelBorder;
  TSharedPtr<SBorder> SidePanelBorder;
  TSharedPtr<SBorder> HandPanelBorder;

  Canvas->AddSlot()
      .Anchors(FAnchors(0.0f, 0.0f))
      .Alignment(FVector2D(0.0f, 0.0f))
      .AutoSize(true)
      [SAssignNew(CommandPanelBorder, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(FLinearColor(0.012f, 0.016f, 0.035f, 0.88f)))
           .Padding(10.0f)
           [SNew(SVerticalBox) +
           SVerticalBox::Slot().AutoHeight()[SAssignNew(CommandBox, SVerticalBox)]]];

  Canvas->AddSlot()
      .Anchors(FAnchors(1.0f, 0.0f))
      .Alignment(FVector2D(1.0f, 0.0f))
      .AutoSize(true)
      [SAssignNew(SidePanelBorder, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(FLinearColor(0.012f, 0.016f, 0.035f, 0.88f)))
           .Padding(10.0f)
           // Bounded scroll region: the open discard browser (both piles +
           // inspector) can exceed 720p; an autosize canvas slot would push
           // chips past the viewport edge where clicks cannot reach.
           [SNew(SBox)
               .MaxDesiredHeight(TAttribute<FOptionalSize>::CreateLambda([]() -> FOptionalSize {
                 if (GEngine && GEngine->GameViewport) {
                   const TSharedPtr<SWidget> ViewportWidget =
                       GEngine->GameViewport->GetGameViewportWidget();
                   if (ViewportWidget.IsValid()) {
                     const float ViewportHeightSu =
                         ViewportWidget->GetCachedGeometry().GetLocalSize().Y;
                     if (ViewportHeightSu > 0.0f) {
                       return FMath::Max(160.0f, ViewportHeightSu - 32.0f);
                     }
                   }
                 }
                 return 600.0f;
               }))
               [SNew(SScrollBox) +
               SScrollBox::Slot()[SAssignNew(PanelsBox, SVerticalBox)]]]];

  Canvas->AddSlot()
      .Anchors(FAnchors(0.5f, 1.0f))
      .Alignment(FVector2D(0.5f, 1.0f))
      .AutoSize(true)
      [SAssignNew(HandPanelBorder, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(FLinearColor(0.012f, 0.016f, 0.035f, 0.88f)))
           .Padding(10.0f)
           [SNew(SVerticalBox) +
           SVerticalBox::Slot().AutoHeight()[SAssignNew(HandBox, SVerticalBox)]]];
  ArtHud.CommandPanel = CommandPanelBorder;
  ArtHud.SidePanel = SidePanelBorder;
  ArtHud.HandPanel = HandPanelBorder;

  Canvas->AddSlot()
      .Anchors(FAnchors(0.5f, 1.0f))
      .Alignment(FVector2D(0.5f, 1.0f))
      .Offset(FVector2D(0.0f, -150.0f))
      .AutoSize(true)
      [SAssignNew(ToastHudBorder, SBorder)
           .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
           .BorderBackgroundColor(FSlateColor(FLinearColor(0.05f, 0.05f, 0.05f, 0.85f)))
           .Padding(10.0f, 6.0f)
           [SNew(SVerticalBox) +
           SVerticalBox::Slot().AutoHeight()
               [SAssignNew(ToastHudLine, STextBlock)
                    .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
                    .ColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.9f, 0.6f)))]]];

  GEngine->GameViewport->AddViewportWidgetContent(Canvas, 1);
}

namespace {
// HUD state markers (P1 acceptance): solid color bars rendered ONLY inside
// the draft panels. The pixel gates in tools/s09 match these exact colors,
// so a board-only capture or a swapped maneuver/discard image fails. The
// colors are deliberately absent from the 3D board palette. Constructed from
// FColor (sRGB bytes): SColorBlock renders linear values and the back buffer
// converts back to sRGB, so the SHOT pixels land on these exact bytes.
constexpr FLinearColor GS09ManeuverMarker(FColor(255, 0, 255, 255));    // #FF00FF
constexpr FLinearColor GS09DiscardMarker(FColor(0, 255, 255, 255));     // #00FFFF
constexpr FLinearColor GS09AttackMarker(FColor(255, 128, 0, 255));      // #FF8000
constexpr FLinearColor GS09DefenseMarker(FColor(255, 64, 64, 255));     // #FF4040
constexpr FLinearColor GS09ResolveMarker(FColor(64, 255, 64, 255));     // #40FF40
constexpr FLinearColor GS09BoostMarker(FColor(255, 255, 64, 255));      // #FFFF40
constexpr FLinearColor GS09ResultMarker(FColor(64, 255, 128, 255));     // #40FF80
// GD-033: revealed attack/defense value text (#7CFC00) - distinct from every
// state marker so the pixel gates can demand it in the revealed resolve shot
// and forbid it in the pre-reveal privacy shot.
constexpr FLinearColor GS09RevealText(FColor(124, 252, 0, 255));        // #7CFC00
constexpr FLinearColor GS09PendingMarker(FColor(64, 128, 255, 255));    // #4080FF
// GD-036: the terminal result screen (#FFD700) - rendered ONLY from the
// authoritative GAME_OVER snapshot (phase + metadata.winnerId). An aborted
// room never reaches this render path, so victory and interruption stay
// visually distinct by construction.
constexpr FLinearColor GS09ResultScreenMarker(FColor(255, 215, 0, 255)); // #FFD700
// GD-036 acceptance: one marker per REQUIRED result element (header /
// outcome / supporting line / button). A capture mid-Slate-paint misses the
// later elements - the pixel gate can demand the COMPLETE panel, not just a
// gold presence (the 11:47 host shot carried only the header + outcome).
constexpr FLinearColor GS09ResultOutcomeMarker(FColor(255, 0, 100, 255));   // #FF0064
constexpr FLinearColor GS09ResultSupportMarker(FColor(0, 255, 160, 255));   // #00FFA0
constexpr FLinearColor GS09ResultButtonMarker(FColor(128, 0, 255, 255));    // #8000FF
// GD-036: the user-facing Lobby entry panel marker (#40C8FF) - gates the
// lobby-return shot on the CLEAN panel, not on leftover duel artifacts.
constexpr FLinearColor GS09LobbyPanelMarker(FColor(64, 200, 255, 255));     // #40C8FF
// GD-035 P3: the owner pending panel's post-reveal combat line (#8040FF) and
// the pending-blocked resolve line (#FF40B0) - distinct from every state
// marker above so pixel gates can demand them exactly where the flag-driven
// render allows them and forbid them everywhere else (pre-reveal privacy).
constexpr FLinearColor GS09RevealLineMarker(FColor(128, 64, 255, 255));   // #8040FF
constexpr FLinearColor GS09ResolveBlockedMarker(FColor(255, 64, 176, 255)); // #FF40B0
// S09 UX: the explicit scheme-picker panel (#A020FF) - each RGB channel is
// >= 32 away from every marker above (pixel gates use +/-16 tolerance).
constexpr FLinearColor GS09SchemeMarker(FColor(160, 32, 255, 255));      // #A020FF
// S10/GD-040: the live-room ABORTED interruption screen (#FF6414) - distinct
// from the #FFD700 result screen so an interrupted match can never be gated
// (or mistaken) for a victory; every channel stays > 16 from all markers
// above (closest is the #FF8000 attack marker: dG=28, dB=20).
constexpr FLinearColor GS10InterruptMarker(FColor(255, 100, 20, 255));   // #FF6414
} // namespace

void AS08FlowGameMode::BuildLobbyPanel() {
  // GD-036: the post-duel Lobby for an authenticated user. The legacy
  // grey-flow form (login + room code + traces) stays behind F10 as the
  // operator overlay; the user-facing panel offers room entry only.
  CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 4)
      [SNew(SBox).WidthOverride(220).HeightOverride(14)
           [SNew(SColorBlock).Color(GS09LobbyPanelMarker)]];
  CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
      // Title tint stays well outside +/-16 of every marker color: a gold
      // tint (255,214,0) collided with the #FFD700 result-header gate.
      [SNew(STextBlock).Text(FText::FromString(TEXT("UNMATCHED")))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
           .ColorAndOpacity(FSlateColor(FLinearColor(0.92f, 0.95f, 1.0f, 1.0f)))];
  CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 8)
      [SNew(STextBlock).Text(FText::FromString(FString::Printf(
           TEXT("signed in as %s"), *Flow->GetUsername())))
           .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
  // S10/GD-039: the same visible mode control as the legacy panel.
  {
    TSharedRef<SHorizontalBox> ModeRow = SNew(SHorizontalBox);
    ModeRow->AddSlot().AutoWidth().Padding(0, 0, 8, 0)
        [SNew(STextBlock).Text(FText::FromString(TEXT("mode:")))];
    ModeRow->AddSlot().AutoWidth().Padding(0, 0, 10, 0)
        [SNew(SCheckBox)
             .IsChecked_Lambda([this]() {
               return LobbyCreateMode == TEXT("ONE_V_ONE") ? ECheckBoxState::Checked
                                                           : ECheckBoxState::Unchecked;
             })
             .OnCheckStateChanged_Lambda([this](ECheckBoxState) {
               LobbyCreateMode = TEXT("ONE_V_ONE");
             })
             .Content()[SNew(STextBlock).Text(FText::FromString(TEXT("ONE_V_ONE")))]];
    ModeRow->AddSlot().AutoWidth()
        [SNew(SCheckBox)
             .IsChecked_Lambda([this]() {
               return LobbyCreateMode == TEXT("VS_AI") ? ECheckBoxState::Checked
                                                       : ECheckBoxState::Unchecked;
             })
             .OnCheckStateChanged_Lambda([this](ECheckBoxState) {
               LobbyCreateMode = TEXT("VS_AI");
             })
             .Content()[SNew(STextBlock).Text(FText::FromString(TEXT("VS_AI (bot)")))]];
    CommandBox->AddSlot().AutoHeight().Padding(0, 2)[ModeRow];
  }
  CommandBox->AddSlot().AutoHeight().Padding(0, 2)
      [SNew(SButton).Text(FText::FromString(TEXT("CREATE ROOM")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->CreateRoom(LobbyCreateMode);
             return FReply::Handled();
           })];
  CommandBox->AddSlot().AutoHeight().Padding(0, 2)
      [SNew(STextBlock)
           .Text_Lambda([this]() {
             return FText::FromString(TEXT("creates: ") + LobbyCreateMode +
                                      (LobbyCreateMode == TEXT("VS_AI")
                                           ? TEXT(" - the server bot joins on start")
                                           : TEXT("")));
           })
           .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
           .ColorAndOpacity(FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f, 1.0f)))];
  TSharedRef<SHorizontalBox> JoinRow = SNew(SHorizontalBox);
  TSharedRef<SEditableTextBox> CodeRef = SNew(SEditableTextBox)
      .HintText(FText::FromString(TEXT("room code")));
  LobbyCodeBox = CodeRef;
  JoinRow->AddSlot().FillWidth(0.55f)[CodeRef];
  JoinRow->AddSlot().AutoWidth().Padding(6, 0, 0, 0)
      [SNew(SButton).Text(FText::FromString(TEXT("JOIN BY CODE")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid() && LobbyCodeBox.IsValid()) {
               Flow->JoinRoomByCode(
                   LobbyCodeBox.Pin()->GetText().ToString().TrimStartAndEnd());
             }
             return FReply::Handled();
           })];
  CommandBox->AddSlot().AutoHeight().Padding(0, 2)[JoinRow];
  CommandBox->AddSlot().AutoHeight().Padding(0, 2)
      [SNew(SButton).Text(FText::FromString(TEXT("RECOVER MY ROOM")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->EnterLobby();
             return FReply::Handled();
           })];
  CommandBox->AddSlot().AutoHeight().Padding(0, 8, 0, 0)
      [SNew(STextBlock).Text(FText::FromString(
           TEXT("create a room and share its code, or join with a friend's code")))
           .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
           .ColorAndOpacity(FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f, 1.0f)))];
}

FString AS08FlowGameMode::CommittedCardLabel(const FString& InstanceId) const {
  for (const FS09PlayerPanel* Panel : {Hud.ViewerPanel(), Hud.OpponentPanel()}) {
    if (!Panel) continue;
    for (const FS09CardView& Card : Panel->Discard) {
      if (Card.InstanceId == InstanceId && !Card.bHidden) return Card.Name;
    }
  }
  return FString(TEXT("committed card"));
}

void AS08FlowGameMode::RefreshHud() {
  SyncCombatFocus();
  if (!HandBox.IsValid() || !PanelsBox.IsValid() || !CommandBox.IsValid()) return;
  HandBox->ClearChildren();
  PanelsBox->ClearChildren();
  CommandBox->ClearChildren();

  // Hidden until the match stream is live (login screens stay clean). An
  // authenticated user in the Lobby gets the room ENTRY panel instead - the
  // lobby must not look like an overlaid in-game diagnostic.
  if (!Hud.bValid) {
    if (Flow.IsValid() && Flow->GetStage() == ES08Stage::Lobby &&
        !Flow->GetUserId().IsEmpty()) {
      BuildLobbyPanel();
    }
    return;
  }

  // ---- GD-036: terminal result screen (top priority; everything else is
  // dead on GAME_OVER - OnSnapshot cleared the drafts, the command gates
  // reject gameplay, board clicks are ignored). Strictly state-driven: a
  // same-seq merge rebuilds the identical panel and cannot double-present. ----
  if (Hud.bGameOver) {
    if (ResultPanelBuiltAtElapsed < 0.0f) {
      ResultPanelBuiltAtElapsed = Elapsed; // settle clock for the capture
    }
    auto AddMarker = [this](const FLinearColor& Color) {
      CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 4)
          [SNew(SBox).WidthOverride(220).HeightOverride(14)
               [SNew(SColorBlock).Color(Color)]];
    };
    auto AddHeader = [this](const FString& Text, const FLinearColor& Tint) {
      CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
          [SNew(STextBlock).Text(FText::FromString(Text))
               .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
               .ColorAndOpacity(FSlateColor(Tint))];
    };
    auto AddLine = [this](const FString& Text) {
      CommandBox->AddSlot().AutoHeight()
          [SNew(STextBlock).Text(FText::FromString(Text))
               .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
    };
    auto AddBigLine = [this](const FString& Text, const FLinearColor& Tint) {
      CommandBox->AddSlot().AutoHeight().Padding(0, 2)
          [SNew(STextBlock).Text(FText::FromString(Text))
               .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
               .ColorAndOpacity(FSlateColor(Tint))];
    };
    AddMarker(GS09ResultScreenMarker);
    AddHeader(TEXT("DUEL RESULT"), FLinearColor(1.0f, 0.84f, 0.0f, 1.0f));
    const FLinearColor OutcomeTint = Hud.bWinnerKnown
                                         ? (Hud.bViewerWon
                                                ? FLinearColor(0.35f, 1.0f, 0.45f, 1.0f)
                                                : FLinearColor(1.0f, 0.45f, 0.45f, 1.0f))
                                         : FLinearColor(0.8f, 0.8f, 0.85f, 1.0f);
    AddMarker(GS09ResultOutcomeMarker);
    AddBigLine(FString::Printf(TEXT("%s%s"), *Hud.OutcomeWord(),
                               Hud.bWinnerKnown
                                   ? *FString::Printf(TEXT(" - %s won the duel"),
                                                      *Hud.WinnerHeroName)
                                   : Hud.bDraw
                                         ? TEXT(" - mutual destruction (server verdict)")
                                         : TEXT(" - outcome unavailable (no server verdict)")),
               OutcomeTint);
    AddMarker(GS09ResultSupportMarker);
    AddLine(FString::Printf(TEXT("seq=%d turnCount=%d - server outcome (GAME_OVER)"),
                            Hud.SequenceNumber, Hud.TurnCount));
    AddLine(TEXT("gameplay input is disabled; L or Enter returns you to the lobby"));
    AddMarker(GS09ResultButtonMarker);
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SButton)
             .ContentPadding(FMargin(14, 8))
             .IsEnabled(!bS09LobbyReturnSent)
             .OnClicked_Lambda([this]() {
               ReturnToLobbyCommand();
               return FReply::Handled();
             })
             [SNew(STextBlock)
                  .Text(FText::FromString(bS09LobbyReturnSent
                                              ? TEXT("RETURNING TO LOBBY...")
                                              : TEXT("RETURN TO LOBBY (L)")))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]];
    return;
  }

  // ---- S10/GD-040: live-room ABORTED interruption screen. Driven ONLY by
  // the authoritative room row (a fresh game(id)/mutation answer - never a
  // snapshot, never a CUE): an interruption is NOT a victory/defeat verdict,
  // the controller gates already block gameplay input, and the leave action
  // remains the only live exit. Rendered above every draft/waiting state. ----
  if (Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Flow->IsRoomAborted()) {
    CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 4)
        [SNew(SBox).WidthOverride(220).HeightOverride(14)
             [SNew(SColorBlock).Color(GS10InterruptMarker)]];
    CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
        [SNew(STextBlock).Text(FText::FromString(TEXT("MATCH INTERRUPTED")))
             .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
             .ColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.62f, 0.12f, 1.0f)))];
    CommandBox->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(
             TEXT("the room was aborted - no winner is declared (this is not a defeat)")))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
    CommandBox->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(
             TEXT("gameplay input is disabled; L or Enter returns you to the lobby")))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SButton)
             .ContentPadding(FMargin(14, 8))
             .IsEnabled(!bS09LobbyReturnSent)
             .OnClicked_Lambda([this]() {
               ReturnToLobbyCommand();
               return FReply::Handled();
             })
             [SNew(STextBlock)
                  .Text(FText::FromString(bS09LobbyReturnSent
                                              ? TEXT("RETURNING TO LOBBY...")
                                              : TEXT("RETURN TO LOBBY (L)")))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]];
    return;
  }

  // ---- GD-037 (ACC-012): reconnect / lost-response recovery overlay. Input
  // is already locked by the controller gates; the banner states WHY. ----
  if (Flow.IsValid() &&
      (Flow->IsAwaitingStateRecovery() ||
       (Flow->GetStage() == ES08Stage::Started && !Flow->IsStreamReady()))) {
    CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 6)
        [SNew(SBorder)
             .BorderBackgroundColor(FLinearColor(0.55f, 0.35f, 0.1f, 0.9f))
             .Padding(8)
               [SNew(STextBlock)
                    .Text(FText::FromString(
                        Flow->IsAwaitingStateRecovery()
                            ? TEXT("RECONNECTING: restoring authoritative state - input locked")
                            : TEXT("RECONNECTING: re-establishing the live stream - input locked")))
                    .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
                    .ColorAndOpacity(FSlateColor(FLinearColor::White))]];
  }

  // ---- own hand strip (exact instance ids - GD-032) ----
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  if (Own) {
    TSharedRef<SHorizontalBox> Strip = SNew(SHorizontalBox);
    int32 Index = 0;
    for (const FS09CardView& Card : Own->Cards) {
      const int32 I = Index++;
      FString Chip;
      if (Card.bHidden) {
        Chip = TEXT("[hidden]");
      } else {
        Chip = FString::Printf(TEXT("%d %s"), I + 1, *Card.Name);
        if (Card.BoostValue > 0) Chip += FString::Printf(TEXT(" B%d"), Card.BoostValue);
        if (Card.bNew) Chip += TEXT(" *NEW*");
        if (CommandUi.BoostCardId == Card.InstanceId) Chip += TEXT(" [BOOST]");
        if (CommandUi.DiscardSelection.Contains(Card.InstanceId)) Chip += TEXT(" [DROP]");
        if (CommandUi.AttackCardId == Card.InstanceId) Chip += TEXT(" [ATK]");
        if (CommandUi.DefenseCardId == Card.InstanceId) Chip += TEXT(" [DEF]");
        if (CommandUi.Mode == ES09CommandMode::SchemeChoice &&
            CommandUi.SchemeCardId == Card.InstanceId) {
          Chip += TEXT(" [SCH]");
        }
        if (CommandUi.PendingCardIds.Contains(Card.InstanceId)) {
          const int32 PickIndex = CommandUi.PendingCardIds.IndexOfByKey(Card.InstanceId);
          Chip += FString::Printf(TEXT(" [PICK%d]"), PickIndex + 1);
        }
      }
      const bool bSelected = InspectedHandIndex == I;
      Strip->AddSlot().AutoWidth().Padding(3)
          [SNew(SButton)
               .ContentPadding(FMargin(10, 8))
               .ButtonColorAndOpacity(
                   FLinearColor(bSelected ? 0.42f : 0.22f, bSelected ? 0.42f : 0.22f,
                                bSelected ? 0.42f : 0.22f, 1.0f))
               .OnClicked_Lambda([this, I]() {
                 HandleHandCardClick(I);
                 return FReply::Handled();
               })
               [SNew(STextBlock).Text(FText::FromString(Chip))
                    .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]];
    }
    HandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 6)
        [SNew(STextBlock)
             .Text(FText::FromString(FString::Printf(
                 TEXT("YOUR HAND  %d/%d   [1-9 inspect | boost/drop while a draft is open]"),
                 Own->HandCount, Own->HandMaxSize)))
             .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))];
    HandBox->AddSlot().AutoHeight()[Strip];
  }

  // ---- counters + inspector (GD-032: opponent hand is a COUNT, never faces) ----
  auto PanelLine = [](const TCHAR* Who, const FS09PlayerPanel& Panel) {
    return FString::Printf(TEXT("%s: hand=%d%s deck=%d%s discard=%d"), Who,
                           Panel.HandCount, Panel.bIsViewer ? TEXT("") : TEXT("(hidden)"),
                           Panel.DeckCount, Panel.bDeckCountStale ? TEXT("~") : TEXT(""),
                           Panel.Discard.Num());
  };
  if (Own) {
    PanelsBox->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(PanelLine(TEXT("you"), *Own)))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
  }
  if (const FS09PlayerPanel* Opponent = Hud.OpponentPanel()) {
    PanelsBox->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(PanelLine(TEXT("opponent"), *Opponent)))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
  }
  PanelsBox->AddSlot().AutoHeight()
      [SNew(STextBlock)
           .Text(FText::FromString(FString::Printf(
               TEXT("seq=%d phase=%s turn=%s actions=%d"),
               Hud.SequenceNumber, *Hud.Phase, Hud.bViewerTurn ? TEXT("you") : TEXT("opp"),
               Hud.ActionsRemaining)))
           .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];

  // ---- GD-032 public discard browser: BOTH piles are public information,
  // so both are browsable; entries are FS09CardView straight from the model -
  // a face-down placeholder renders and inspects as faceless by construction
  // (selection is read-only: no draft, hand pick or server command changes). ----
  PanelsBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
      [SNew(SButton)
           .ContentPadding(FMargin(8, 3))
           .ButtonColorAndOpacity(
               FLinearColor(bDiscardBrowserOpen ? 0.32f : 0.20f, bDiscardBrowserOpen ? 0.32f : 0.20f,
                            bDiscardBrowserOpen ? 0.32f : 0.20f, 1.0f))
           .OnClicked_Lambda([this]() {
             bDiscardBrowserOpen = !bDiscardBrowserOpen;
             DiscardBrowserIndex = -1;
             RefreshHud();
             return FReply::Handled();
           })
           [SNew(STextBlock)
                .Text(FText::FromString(FString::Printf(
                    TEXT("%s DISCARD PILES  (D)"),
                    bDiscardBrowserOpen ? TEXT("HIDE") : TEXT("BROWSE"))))
                .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))]];
  if (bDiscardBrowserOpen) {
    for (int32 Pile = 0; Pile < 2; ++Pile) {
      const FS09PlayerPanel* Panel =
          Pile == 0 ? Hud.ViewerPanel() : Hud.OpponentPanel();
      if (!Panel) continue;
      PanelsBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
          [SNew(STextBlock)
               .Text(FText::FromString(FString::Printf(
                   TEXT("%s discard (%d)%s"), Pile == 0 ? TEXT("your") : TEXT("opponent"),
                   Panel->Discard.Num(), Panel->bDiscardStale ? TEXT(" ~") : TEXT(""))))
               .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
               .ColorAndOpacity(FSlateColor(FLinearColor(0.85f, 0.85f, 0.65f)))];
      if (Panel->Discard.Num() == 0) {
        PanelsBox->AddSlot().AutoHeight()
            [SNew(STextBlock).Text(FText::FromString(TEXT("(empty)")))
                 .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
                 .ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f, 1.0f)))];
        continue;
      }
      TSharedRef<SWrapBox> Wrap = SNew(SWrapBox);
      int32 ChipIndex = 0;
      for (const FS09CardView& Card : Panel->Discard) {
        const int32 P = Pile;
        const int32 I = ChipIndex++;
        // Hidden entry: position number only - no name, no values, ever.
        const FString Chip = Card.bHidden
                                 ? FString::Printf(TEXT("%d face-down"), I + 1)
                                 : FString::Printf(TEXT("%d %s"), I + 1, *Card.Name);
        const bool bChipSelected = Pile == DiscardBrowserPile &&
                                   I == DiscardBrowserIndex;
        Wrap->AddSlot().Padding(2)
            [SNew(SButton)
                 .ContentPadding(FMargin(8, 3))
                 .ButtonColorAndOpacity(
                     FLinearColor(bChipSelected ? 0.42f : 0.22f, bChipSelected ? 0.42f : 0.22f,
                                  bChipSelected ? 0.42f : 0.22f, 1.0f))
                 .OnClicked_Lambda([this, P, I]() {
                   HandleDiscardCardClick(P, I);
                   return FReply::Handled();
                 })
                 [SNew(STextBlock).Text(FText::FromString(Chip))
                      .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))]];
      }
      PanelsBox->AddSlot().AutoHeight()
          [SNew(SBox).WidthOverride(370)[Wrap]];
    }
    PanelsBox->AddSlot().AutoHeight().Padding(0, 4, 0, 0)
        [SNew(STextBlock)
             .Text(FText::FromString(
                 TEXT("Up/Down switch pile; Left/Right or click selects; Esc closes")))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 11))
             .ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f, 1.0f)))];
  }

  if (bInspecting) {
    static const TCHAR* SourceLabels[3] = {TEXT("hand"), TEXT("your discard"),
                                           TEXT("opponent discard")};
    const int32 Source = FMath::Clamp(InspectedSource, 0, 2);
    TArray<FString> Lines;
    BuildInspectorLines(InspectedCard, Lines);
    TSharedRef<SVerticalBox> InspectorBox = SNew(SVerticalBox);
    InspectorBox->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
        [SNew(STextBlock)
             .Text(FText::FromString(FString::Printf(TEXT("inspector: %s"),
                                                     SourceLabels[Source])))
             .Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
             .ColorAndOpacity(FSlateColor(FLinearColor(0.85f, 0.85f, 0.65f)))];
    for (int32 LineIndex = 0; LineIndex < Lines.Num(); ++LineIndex) {
      InspectorBox->AddSlot().AutoHeight()
          [SNew(STextBlock)
               .Text(FText::FromString(Lines[LineIndex]))
               .Font(FCoreStyle::GetDefaultFontStyle(
                   LineIndex == 0 ? "Bold" : "Regular", 12))
               .AutoWrapText(true)
               .ColorAndOpacity(FSlateColor(FLinearColor(0.92f, 0.92f, 0.92f, 1.0f)))];
    }
    PanelsBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SBorder)
             .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
             .BorderBackgroundColor(FSlateColor(FLinearColor(0.05f, 0.05f, 0.08f, 0.85f)))
             .Padding(6)
             [SNew(SBox).WidthOverride(370)[InspectorBox]]];
  }

  // ---- command panel (GD-033). Fonts >= 12pt (16px @96DPI) and button
  // targets >= 32px tall: P1 acceptance for 1280x720 readability. ----
  const bool bDraft = CommandUi.Mode == ES09CommandMode::ManeuverDraft;
  const bool bDiscard = CommandUi.Mode == ES09CommandMode::DiscardDraft;
  const bool bBusy = CommandUi.bCommandInFlight;
  auto AddMarker = [this](const FLinearColor& Color) {
    CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 4)
        [SNew(SBox).WidthOverride(220).HeightOverride(14)
             [SNew(SColorBlock).Color(Color)]];
  };
  auto AddHeader = [this](const FString& Text, const FLinearColor& Tint) {
    CommandBox->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
        [SNew(STextBlock).Text(FText::FromString(Text))
             .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
             .ColorAndOpacity(FSlateColor(Tint))];
  };
  auto AddLine = [this](const FString& Text) {
    CommandBox->AddSlot().AutoHeight()
        [SNew(STextBlock).Text(FText::FromString(Text))
             .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))];
  };
  auto AddBigLine = [this](const FString& Text, const FLinearColor& Tint) {
    CommandBox->AddSlot().AutoHeight().Padding(0, 2)
        [SNew(STextBlock).Text(FText::FromString(Text))
             .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
             .ColorAndOpacity(FSlateColor(Tint))];
  };

  // ---- GD-034: combat result summary (privacy-safe: own values + damage) ----
  // Only while NO command panel is open: the 20s result window outlives combat,
  // and a later draft (e.g. the next turn's attack draft) owns the marker frame.
  if (LastCombatResult.bValid && LastCombatResult.ShownAt >= 0.0f &&
      Elapsed - LastCombatResult.ShownAt < 20.0f &&
      CommandUi.Mode == ES09CommandMode::None) {
    AddMarker(GS09ResultMarker);
    AddHeader(TEXT("COMBAT RESULT"), FLinearColor(0.25f, 1.0f, 0.5f, 1.0f));
    AddBigLine(LastCombatResult.OutcomeLine, FLinearColor(1.0f, 1.0f, 1.0f, 1.0f));
  }

  if (bDraft) {
    AddMarker(GS09ManeuverMarker);
    AddHeader(TEXT("MANEUVER DRAFT - MOVE FIGHTERS"),
              FLinearColor(1.0f, 0.6f, 1.0f, 1.0f));
    AddLine(FString::Printf(TEXT("moves drafted: %d   boost: %s"), CommandUi.Moves.Num(),
                            CommandUi.BoostCardId.IsEmpty() ? TEXT("none") : TEXT("card")));
    AddLine(TEXT("click an own fighter, then a green cell; 1-9 boost card; Enter confirm; Esc cancel"));
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy)
                  .OnClicked_Lambda([this]() {
                    ConfirmDraft();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("CONFIRM MANEUVER (Enter)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]] +
         SHorizontalBox::Slot().AutoWidth()
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .OnClicked_Lambda([this]() {
                    CancelDraft();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("CLEAR DRAFT (Esc)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]]];
  } else if (bDiscard) {
    const int32 Need = CommandUi.PendingDiscard.Count;
    const int32 Have = CommandUi.DiscardSelection.Num();
    AddMarker(GS09DiscardMarker);
    AddHeader(TEXT("MANDATORY DISCARD - HAND OVER LIMIT"),
              FLinearColor(0.6f, 1.0f, 1.0f, 1.0f));
    AddBigLine(FString::Printf(TEXT("CHOOSE %d CARD%s: selected %d/%d (%d more)"), Need,
                               Need == 1 ? TEXT("") : TEXT("S"), Have, Need, Need - Have),
               FLinearColor(1.0f, 1.0f, 1.0f, 1.0f));
    AddLine(TEXT("click cards or press 1-9 to toggle [DROP]; Enter confirms"));
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SButton)
             .ContentPadding(FMargin(14, 8))
             .IsEnabled(Have == Need && !bBusy)
             .OnClicked_Lambda([this]() {
               ConfirmDraft();
               return FReply::Handled();
             })
             [SNew(STextBlock)
                  .Text(FText::FromString(FString::Printf(
                      TEXT("CONFIRM DISCARD %d/%d (Enter)"), Have, Need)))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]];
  } else if (CommandUi.Mode == ES09CommandMode::AttackDraft) {
    auto FighterLabel = [this](const FString& Id) {
      for (const FS08BoardFighter& Entry : Fighters) {
        if (Entry.Id == Id) return Entry.Label;
      }
      return FString(TEXT("-"));
    };
    AddMarker(GS09AttackMarker);
    AddHeader(TEXT("ATTACK DRAFT - PICK ATTACKER, TARGET, CARD"),
              FLinearColor(1.0f, 0.6f, 0.2f, 1.0f));
    AddLine(FString::Printf(TEXT("attacker: %s   target: %s   card: %s"),
                            *FighterLabel(CommandUi.AttackAttackerId),
                            *FighterLabel(CommandUi.AttackTargetId),
                            CommandUi.AttackCardId.IsEmpty() ? TEXT("-") : TEXT("picked")));
    if (!CommandUi.AttackAttackerId.IsEmpty()) {
      // ENV-O6 / GAP-023: exactly the set SelectTarget/ConfirmAttack accept.
      const FS08BoardFighter* Attacker = FindFighter(CommandUi.AttackAttackerId);
      FString InRange;
      for (const FString& TargetId :
           FS09CommandUi::LegalAttackTargets(BoardModel, Fighters, CommandUi.AttackAttackerId)) {
        const FS08BoardFighter* Target = FindFighter(TargetId);
        if (!Attacker || !Target) continue;
        InRange += FString::Printf(
            TEXT("%s%s (%s)"), InRange.IsEmpty() ? TEXT("") : TEXT(", "), *Target->Label,
            FS09CommandUi::IsZoneOnlyTarget(BoardModel, *Attacker, *Target) ? TEXT("same zone")
                                                                            : TEXT("adjacent"));
      }
      AddLine(FString::Printf(TEXT("targets in range: %s"), InRange.IsEmpty() ? TEXT("-") : *InRange));
    }
    AddLine(TEXT("click an own fighter with an enemy in range (melee: adjacent; ranged: adjacent or same zone), click the enemy, pick 1-9; Enter attacks; A/Esc closes"));
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy)
                  .OnClicked_Lambda([this]() {
                    ConfirmCombat();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("ATTACK (Enter)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]] +
         SHorizontalBox::Slot().AutoWidth()
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .OnClicked_Lambda([this]() {
                    CancelDraft();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("CLOSE DRAFT (Esc)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]]];
  } else if (CommandUi.Mode == ES09CommandMode::SchemeChoice) {
    // S09 UX: the explicit picker. The selected EXACT card is spelled out -
    // legibility requirement from the wrong-card-spend review.
    FString Selected = TEXT("-");
    if (Own && !CommandUi.SchemeCardId.IsEmpty()) {
      for (const FS09CardView& Card : Own->Cards) {
        if (Card.InstanceId == CommandUi.SchemeCardId) {
          Selected = FString::Printf(TEXT("%s [%s]"), *Card.Name,
                                     Card.BannerName.IsEmpty() ? TEXT("any") : *Card.BannerName);
        }
      }
      if (Selected == TEXT("-")) Selected = TEXT("(selection stale - pick again)");
    }
    AddMarker(GS09SchemeMarker);
    AddHeader(TEXT("SCHEME CHOICE - PLAY ONE SCHEME CARD"),
              FLinearColor(0.72f, 0.35f, 1.0f, 1.0f));
    AddBigLine(FString::Printf(TEXT("selected: %s"), *Selected),
               FLinearColor(1.0f, 1.0f, 1.0f, 1.0f));
    AddLine(TEXT("click a scheme card or press 1-9; Enter plays THAT EXACT card; G or Esc cancels"));
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy && !CommandUi.SchemeCardId.IsEmpty())
                  .OnClicked_Lambda([this]() {
                    ConfirmSchemeCommand();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("PLAY SELECTED SCHEME (Enter)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]] +
         SHorizontalBox::Slot().AutoWidth()
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .OnClicked_Lambda([this]() {
                    PlaySchemeCommand(); // G semantics: close without sending
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("CANCEL (G/Esc)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]]];
  } else if (CommandUi.Mode == ES09CommandMode::CombatDefense) {
    const double Left = CommandUi.Combat.bHasTimeoutAt
                            ? CommandUi.Combat.SecondsUntilDeadline() : -1.0;
    AddMarker(GS09DefenseMarker);
    AddHeader(TEXT("YOU ARE ATTACKED - DEFENSE WINDOW"),
              FLinearColor(1.0f, 0.4f, 0.4f, 1.0f));
    AddBigLine(FString::Printf(TEXT("server deadline: %s"),
                               Left > 0.0 ? *FString::Printf(TEXT("%.0fs left"), Left)
                                          : TEXT("EXPIRED - the server resolves")),
               FLinearColor(1.0f, 1.0f, 1.0f, 1.0f));
    // Own committed view only: never the attacker's card/value pre-reveal.
    AddLine(FString::Printf(TEXT("defense card: %s"),
                            CommandUi.DefenseCardId.IsEmpty() ? TEXT("-") : TEXT("picked")));
    AddLine(TEXT("1-9 picks a defense card; Enter defends; N = NO DEFENSE"));
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy && Left > 0.0)
                  .OnClicked_Lambda([this]() {
                    ConfirmCombat();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("PLAY DEFENSE (Enter)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]] +
         SHorizontalBox::Slot().AutoWidth()
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy && Left > 0.0)
                  .OnClicked_Lambda([this]() {
                    NoDefenseCommand();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("NO DEFENSE (N)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]]];
  } else if (CommandUi.Mode == ES09CommandMode::CombatResolve) {
    const double Left = CommandUi.Combat.bHasTimeoutAt
                            ? CommandUi.Combat.SecondsUntilDeadline() : -1.0;
    AddMarker(GS09ResolveMarker);
    AddHeader(TEXT("COMBAT RESOLVE WINDOW"), FLinearColor(0.4f, 1.0f, 0.4f, 1.0f));
    AddBigLine(FString::Printf(TEXT("server deadline: %s"),
                               Left > 0.0 ? *FString::Printf(TEXT("%.0fs left"), Left)
                                          : TEXT("EXPIRED - the server resolves")),
               FLinearColor(1.0f, 1.0f, 1.0f, 1.0f));
    // Reveal state: bRevealed is derived from THIS body's visible fields.
    // Rendering is strictly flag-driven (privacy contract, S08Contracts):
    // pre-reveal the server strips the opponent's card id AND value from
    // this body, so only the OWN committed card can ever render; post-reveal
    // both committed identities + printed values are public.
    {
      const FS08CombatInfo& Combat = CommandUi.Combat;
      const FString AttackLine = FString::Printf(
          TEXT("attack: %s  A%d%s"),
          *CommittedCardLabel(Combat.AttackerCardId),
          Combat.AttackValue,
          Combat.bHasBoostValue
              ? *FString::Printf(TEXT(" + boost %d"), Combat.BoostValue)
              : TEXT(""));
      const FString DefenseLine =
          Combat.bHasDefenderCard
              ? FString::Printf(TEXT("defense: %s  D%d"),
                                *CommittedCardLabel(Combat.DefenderCardId),
                                Combat.DefenseValue)
              : FString::Printf(
                    TEXT("defense: NO CARD%s"),
                    Hud.Phase == TEXT("COMBAT_RESOLVE")
                        ? TEXT(" (defender committed no defense)")
                        : TEXT(" (defender has not responded yet)"));
      if (Combat.bRevealed) {
        AddMarker(GS09RevealText); // pixel-exact #7CFC00 block: the reveal gate
        AddBigLine(TEXT("REVEALED - both committed cards:"), GS09RevealText);
        AddBigLine(AttackLine, GS09RevealText);
        AddBigLine(DefenseLine, GS09RevealText);
        // Values are public after the reveal - trace once per combat so the
        // published log proves the panel rendered them (rate-limited: the
        // combat panels re-render on the 0.25s deadline tick).
        const FString TraceKey = FString::Printf(
            TEXT("%s:%d"), *Combat.TargetFighterId, Flow->GetAppliedSnapshot().SequenceNumber);
        if (TraceKey != S09RevealTraceKey) {
          S09RevealTraceKey = TraceKey;
          FS08Trace::Write(FString::Printf(
              TEXT("RESOLVE panel revealed: A%d%s vs %s"),
              Combat.AttackValue,
              Combat.bHasBoostValue ? *FString::Printf(TEXT("+B%d"), Combat.BoostValue) : TEXT(""),
              Combat.bHasDefenderCard ? *FString::Printf(TEXT("D%d"), Combat.DefenseValue)
                                      : TEXT("no-defense")));
        }
      } else {
        if (Combat.bHasAttackerCard) {
          AddLine(FString::Printf(TEXT("your attack committed: %s (A%d%s)"),
                                  *CommittedCardLabel(Combat.AttackerCardId),
                                  Combat.AttackValue,
                                  Combat.bHasBoostValue
                                      ? *FString::Printf(TEXT(" + boost %d"), Combat.BoostValue)
                                      : TEXT("")));
        } else if (Combat.bHasDefenderCard) {
          AddLine(FString::Printf(TEXT("your defense committed: %s (D%d)"),
                                  *CommittedCardLabel(Combat.DefenderCardId),
                                  Combat.DefenseValue));
        }
        AddLine(TEXT("the opponent's committed card (if any) stays hidden until the reveal"));
      }
    }
    // A non-empty pending queue blocks resolve on BOTH seats (server gate:
    // 'Resolve the pending choice first') - mirror that in the button state
    // instead of rendering an enabled control that only toasts a rejection.
    const bool bPendingBlocksResolve = CommandUi.PendingQueue.Num() > 0;
    if (bPendingBlocksResolve) {
      AddMarker(GS09ResolveBlockedMarker); // pixel-exact #FF40B0: the block gate
      AddBigLine(FString::Printf(
                      TEXT("RESOLVE blocked - a pending choice (%s) must be answered first"),
                      *CommandUi.PendingQueue[0].Type),
                  GS09ResolveBlockedMarker);
      // Trace once per blocking head (the panels re-render every 0.25s tick):
      // the published log proves the non-owning seat rendered the block.
      const FString BlockedTraceKey =
          FString::Printf(TEXT("blk:%s"), *CommandUi.PendingQueue[0].Id);
      if (BlockedTraceKey != S09ResolveBlockedTraceKey) {
        S09ResolveBlockedTraceKey = BlockedTraceKey;
        FS08Trace::Write(FString::Printf(
            TEXT("RESOLVE panel blocked by pending (type=%s id=%s)"),
            *CommandUi.PendingQueue[0].Type, *CommandUi.PendingQueue[0].Id));
      }
    } else {
      AddLine(TEXT("R resolves the combat (any participant); the attacker cannot close the defense window"));
    }
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SButton)
             .ContentPadding(FMargin(14, 8))
             .IsEnabled(!bBusy && !bPendingBlocksResolve)
             .OnClicked_Lambda([this]() {
               ResolveCombatCommand();
               return FReply::Handled();
             })
             [SNew(STextBlock).Text(FText::FromString(TEXT("RESOLVE COMBAT (R)")))
                  .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]];
  } else if (CommandUi.Mode == ES09CommandMode::PendingChoice) {
    // GD-035: the server waits on THIS viewer's queue head. A MANDATORY
    // choice renders louder (red header) than any normal HUD/inspector line.
    const FS08PendingEffect& Pending = CommandUi.PendingChoice;
    AddMarker(GS09PendingMarker);
    AddHeader(FString::Printf(TEXT("PENDING CHOICE - %s  [%s]"), *Pending.Type,
                              Pending.bOptional ? TEXT("optional - X declines")
                                                : TEXT("MANDATORY")),
              Pending.bOptional ? FLinearColor(1.0f, 1.0f, 0.4f, 1.0f)
                                : FLinearColor(1.0f, 0.35f, 0.35f, 1.0f));
    if (!Pending.Text.IsEmpty()) AddLine(Pending.Text);
    if (CommandUi.PendingQueue.Num() > 1) {
      AddLine(FString::Printf(TEXT("queue: %d choices (this one first)"),
                              CommandUi.PendingQueue.Num()));
    }
    // Post-reveal pause (e.g. the owner's BOOST_CHOICE): the committed
    // identities/values are already PUBLIC (both seats render them in the
    // resolve window) - mirror them here so the choosing seat sees the combat
    // it is deciding about. Pre-reveal NOTHING renders: the flag-driven
    // privacy contract strips the opponent data before it can reach this UI.
    if (CommandUi.Combat.bRevealed) {
      const FS08CombatInfo& Combat = CommandUi.Combat;
      AddMarker(GS09RevealLineMarker); // pixel-exact #8040FF: the owner line gate
      AddBigLine(
          FString::Printf(
              TEXT("REVEALED combat: attack %s A%d%s vs %s"),
              *CommittedCardLabel(Combat.AttackerCardId), Combat.AttackValue,
              Combat.bHasBoostValue
                  ? *FString::Printf(TEXT("+B%d"), Combat.BoostValue) : TEXT(""),
              Combat.bHasDefenderCard
                  ? *FString::Printf(TEXT("defense %s D%d"),
                                     *CommittedCardLabel(Combat.DefenderCardId),
                                     Combat.DefenseValue)
                  : TEXT("no defense")),
          GS09RevealLineMarker);
      // Trace once per combat: proves the owner pending panel rendered the
      // already-public values (rate-limited against the 0.25s deadline tick).
      const FString PendingRevealKey = FString::Printf(
          TEXT("pnd:%s:%d"), *Combat.TargetFighterId,
          Flow->GetAppliedSnapshot().SequenceNumber);
      if (PendingRevealKey != S09PendingRevealTraceKey) {
        S09PendingRevealTraceKey = PendingRevealKey;
        FS08Trace::Write(FString::Printf(
            TEXT("PENDING panel revealed: attack A%d%s vs %s"),
            Combat.AttackValue,
            Combat.bHasBoostValue
                ? *FString::Printf(TEXT("+B%d"), Combat.BoostValue) : TEXT(""),
            Combat.bHasDefenderCard
                ? *FString::Printf(TEXT("D%d"), Combat.DefenseValue)
                : TEXT("no-defense")));
      }
    }
    const FString& PendingType = Pending.Type;
    if (PendingType == TEXT("MOVE") || PendingType == TEXT("PLACE")) {
      FString FighterLabel;
      for (const FS08BoardFighter& Entry : Fighters) {
        if (Entry.Id == CommandUi.PendingFighterId) FighterLabel = Entry.Label;
      }
      AddLine(FString::Printf(TEXT("fighter: %s   destination: %s"),
                              *FighterLabel,
                              CommandUi.bPendingCellSet
                                  ? *FString::Printf(TEXT("(%d,%d)"), CommandUi.PendingCellX,
                                                     CommandUi.PendingCellY)
                                  : TEXT("-")));
      if (PendingType == TEXT("MOVE")) {
        AddLine(FString::Printf(TEXT("move up to %d - click the fighter, then a green cell"),
                                Pending.bHasValue ? Pending.Value : 1));
      } else {
        AddLine(Pending.bRestoreFullHealth
                    ? TEXT("place the defeated fighter (full health) - click it, then a green cell")
                    : TEXT("place: click the fighter, then a green cell"));
        if (!Pending.ZoneFighterName.IsEmpty()) {
          AddLine(FString::Printf(TEXT("restricted to %s's zone (green cells)"),
                                  *Pending.ZoneFighterName));
        }
      }
    } else if (PendingType == TEXT("CHOOSE_SPACE")) {
      AddLine(FString::Printf(TEXT("stage %d - %s   cell: %s"), Pending.Stage,
                              Pending.Stage == 2 ? TEXT("adjacent to the first pick")
                                                 : TEXT("inside the zone"),
                              CommandUi.bPendingCellSet
                                  ? *FString::Printf(TEXT("(%d,%d)"), CommandUi.PendingCellX,
                                                     CommandUi.PendingCellY)
                                  : TEXT("-")));
      if (Pending.Stage == 2 && Pending.bHasAnchor) {
        AddLine(FString::Printf(TEXT("anchor: (%d,%d) - green cells are the legal picks"),
                                Pending.AnchorX, Pending.AnchorY));
      } else if (!Pending.ZoneFighterName.IsEmpty()) {
        AddLine(FString::Printf(TEXT("pick any green cell in %s's zone"), *Pending.ZoneFighterName));
      }
      if (Pending.bHasDamage) {
        AddLine(FString::Printf(TEXT("then %d damage to every enemy on both cells"), Pending.Damage));
      }
    } else if (PendingType == TEXT("TARGET_FIGHTER")) {
      FString FighterLabel;
      for (const FS08BoardFighter& Entry : Fighters) {
        if (Entry.Id == CommandUi.PendingFighterId) FighterLabel = Entry.Label;
      }
      AddLine(FString::Printf(TEXT("target: %s%s"), *FighterLabel,
                              Pending.bHasDamage
                                  ? *FString::Printf(TEXT("  (%d damage)"), Pending.Damage)
                                  : TEXT("")));
      AddLine(TEXT("click a highlighted fighter; Enter confirms"));
    } else if (PendingType == TEXT("CHOOSE_ONE")) {
      AddLine(FString::Printf(TEXT("choose %d option(s) - keys 1-%d or click"),
                              Pending.ChooseCount, Pending.Options.Num()));
      for (int32 OptionIdx = 0; OptionIdx < Pending.Options.Num(); OptionIdx++) {
        const int32 StableIndex = Pending.Options[OptionIdx].Index;
        CommandBox->AddSlot().AutoHeight().Padding(6, 2)
            [SNew(SButton)
                 .ContentPadding(FMargin(10, 6))
                 .ButtonColorAndOpacity(FLinearColor(
                     CommandUi.PendingOptionIndex == OptionIdx ? 0.45f : 0.22f,
                     CommandUi.PendingOptionIndex == OptionIdx ? 0.45f : 0.22f,
                     CommandUi.PendingOptionIndex == OptionIdx ? 0.45f : 0.22f, 1.0f))
                 .OnClicked_Lambda([this, OptionIdx]() {
                   FString Reason;
                   if (CommandUi.SelectPendingOption(OptionIdx, Reason)) {
                     Toast = TEXT("option selected - Enter confirms");
                   } else {
                     Toast = TEXT("option rejected: ") + Reason;
                   }
                   ToastUntil = Elapsed + 3.0f;
                   RefreshHud();
                   return FReply::Handled();
                 })
                 [SNew(STextBlock)
                      .Text(FText::FromString(FString::Printf(
                          TEXT("%d. %s%s"), OptionIdx + 1,
                          *Pending.Options[OptionIdx].Label,
                          CommandUi.PendingOptionIndex == OptionIdx ? TEXT("  [SELECTED]")
                                                                    : TEXT(""))))
                      .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]];
        (void)StableIndex;
      }
    } else if (PendingType == TEXT("DISCARD_CARDS")) {
      const int32 Need = Pending.bHasValue ? Pending.Value : 1;
      AddLine(FString::Printf(TEXT("discard exactly %d of your cards - 1-9 toggles (%d chosen)"),
                              Need, CommandUi.PendingCardIds.Num()));
    } else if (PendingType == TEXT("BOOST_CHOICE")) {
      AddLine(FString::Printf(TEXT("boost with exactly 1 hand card (%d chosen) - 1-9 toggles"),
                              CommandUi.PendingCardIds.Num()));
    } else if (PendingType == TEXT("DECK_TOP_PICK")) {
      TArray<FS09CardView> Revealed;
      if (CommandUi.PendingRevealedCards(Revealed)) {
        const bool bOrder = Pending.Mode == TEXT("ORDER");
        const int32 Need = bOrder ? Revealed.Num()
                                  : (Pending.bHasValue ? Pending.Value : 2);
        AddLine(bOrder
            ? FString::Printf(
                  TEXT("return order: click ALL %d revealed (pick sequence = top to bottom)"), Need)
            : FString::Printf(
                  TEXT("take exactly %d of the revealed cards into your hand"), Need));
        for (const FS09CardView& Card : Revealed) {
          const int32 PickIndex = CommandUi.PendingCardIds.IndexOfByKey(Card.InstanceId);
          CommandBox->AddSlot().AutoHeight().Padding(6, 2)
              [SNew(SButton)
                   .ContentPadding(FMargin(10, 6))
                   .ButtonColorAndOpacity(FLinearColor(
                       PickIndex >= 0 ? 0.45f : 0.22f, PickIndex >= 0 ? 0.45f : 0.22f,
                       PickIndex >= 0 ? 0.45f : 0.22f, 1.0f))
                   .OnClicked_Lambda([this, InstanceId = Card.InstanceId]() {
                     FString Reason;
                     if (CommandUi.TogglePendingCard(InstanceId, EffectiveSnapshot(), Reason)) {
                       Toast = TEXT("revealed pick toggled");
                     } else {
                       Toast = TEXT("pick rejected: ") + Reason;
                     }
                     ToastUntil = Elapsed + 3.0f;
                     RefreshHud();
                     return FReply::Handled();
                   })
                   [SNew(STextBlock)
                        .Text(FText::FromString(FString::Printf(
                            TEXT("%s%s"), *Card.Name,
                            PickIndex >= 0 ? *FString::Printf(TEXT("  [#%d]"), PickIndex + 1)
                                           : TEXT(""))))
                        .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]];
        }
      } else {
        AddLine(TEXT("revealed cards are hidden from this seat"));
      }
    }
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy)
                  .OnClicked_Lambda([this]() {
                    ConfirmCombat();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("CONFIRM (Enter)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]] +
         SHorizontalBox::Slot().AutoWidth()
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy && CommandUi.PendingChoice.bOptional)
                  .OnClicked_Lambda([this]() {
                    DeclinePendingChoiceCommand();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("DECLINE (X)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]]];
  } else if (CommandUi.bHasPendingChoice) {
    // GD-035: the head belongs to the OPPONENT - their choice, never ours.
    AddHeader(FString::Printf(TEXT("WAITING - opponent's choice (%s)"),
                              *CommandUi.PendingChoice.Type),
              FLinearColor(1.0f, 0.7f, 0.4f, 1.0f));
    if (CommandUi.PendingChoice.Type == TEXT("DECK_TOP_PICK") &&
        CommandUi.PendingChoice.bHasRevealedCount) {
      AddLine(FString::Printf(TEXT("%d card(s) revealed to them (faces hidden)"),
                              CommandUi.PendingChoice.RevealedCount));
    }
    AddLine(TEXT("the server blocks further actions until the queue drains"));
  } else if (Hud.bViewerTurn) {
    AddHeader(TEXT("YOUR TURN"), FLinearColor(0.7f, 1.0f, 0.7f, 1.0f));
    AddLine(FString::Printf(TEXT("actions left: %d   phase: %s"),
                            FMath::Max(0, Hud.ActionsRemaining), *Hud.Phase));
    AddLine(TEXT("M begin maneuver  |  A attack draft  |  G scheme picker  |  E end turn"));
    CommandBox->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
        [SNew(SHorizontalBox) +
         SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy && Hud.ActionsRemaining > 0)
                  .OnClicked_Lambda([this]() {
                    BeginManeuverCommand();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("BEGIN MANEUVER (M)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))]] +
         SHorizontalBox::Slot().AutoWidth()
             [SNew(SButton)
                  .ContentPadding(FMargin(14, 8))
                  .IsEnabled(!bBusy && Hud.ActionsRemaining == 0)
                  .OnClicked_Lambda([this]() {
                    EndTurnCommand();
                    return FReply::Handled();
                  })
                  [SNew(STextBlock).Text(FText::FromString(TEXT("END TURN (E)")))
                       .Font(FCoreStyle::GetDefaultFontStyle("Regular", 14))]]];
  } else {
    AddHeader(TEXT("OPPONENT'S TURN"), FLinearColor(1.0f, 0.8f, 0.6f, 1.0f));
    if (Flow.IsValid() && Flow->IsBotActing()) {
      // S10/GD-039: the waiting indicator follows the AUTHORITATIVE turn
      // owner (applied snapshot), never a fixed timer.
      AddLine(TEXT("VS_AI: the server bot is acting - waiting for its move"));
    }
    AddLine(FString::Printf(TEXT("seq=%d - waiting for the authoritative stream"),
                            Hud.SequenceNumber));
  }
}

void AS08FlowGameMode::RefreshUi() {
  UpdateLegacyRootVisibility();
  if (ToastHudLine.IsValid()) {
    ToastHudLine.Pin()->SetText(FText::FromString(Toast));
  }
  if (ToastHudBorder.IsValid()) {
    ToastHudBorder.Pin()->SetVisibility(
        Toast.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible);
  }
  if (StatusLine.IsValid()) {
    const TCHAR* Names[] = {TEXT("BOOT"), TEXT("LOGIN done"), TEXT("LOBBY"), TEXT("ROOM"),
                            TEXT("STARTED"), TEXT("FAILED")};
    StatusLine.Pin()->SetText(FText::FromString(FString::Printf(
        TEXT("stage: %s   user: %s"), Names[static_cast<int32>(Flow->GetStage())],
        *Flow->GetUsername())));
  }
  if (RoomLine.IsValid() && Flow.IsValid()) {
    const FS08RoomState& R = Flow->GetRoom();
    RoomLine.Pin()->SetText(FText::FromString(FString::Printf(
        TEXT("room %s  code %s  status %s  mode %s"), *R.GameId, *R.Code, *R.Status, *R.Mode)));
  }
  if (PlayersLine.IsValid() && Flow.IsValid()) {
    const FS08RoomState& R = Flow->GetRoom();
    FString Line;
    for (const FS08RoomPlayer& P : R.Players) {
      if (!Line.IsEmpty()) Line += TEXT(" | ");
      Line += FString::Printf(TEXT("%s%s hero=%s ready=%d"), *P.Username,
                              R.IsHost(P.UserId) ? TEXT("(host)") : TEXT(""),
                              *P.HeroId, P.bIsReady ? 1 : 0);
    }
    PlayersLine.Pin()->SetText(FText::FromString(Line));
  }
  if (BoardLine.IsValid() && Flow.IsValid()) {
    FString Line = FString::Printf(TEXT("board %dx%d  fighters %d  seq %d  phase %s  turn %s"),
                                   BoardModel.Width, BoardModel.Height, Fighters.Num(),
                                   Flow->GetAppliedSnapshot().SequenceNumber,
                                   *Flow->GetAppliedSnapshot().Phase,
                                   Flow->IsMyTurn() ? TEXT("yours") : TEXT("opponent"));
    if (!SelectedFighterId.IsEmpty()) {
      for (const FS08BoardFighter& Fighter : Fighters) {
        if (Fighter.Id == SelectedFighterId) {
          Line += FString::Printf(TEXT("  selected %s [%s] at (%d,%d)"), *Fighter.Label,
                                  *Fighter.Id, Fighter.X, Fighter.Y);
        }
      }
    }
    BoardLine.Pin()->SetText(FText::FromString(Line));
  }
  if (ToastLine.IsValid()) {
    ToastLine.Pin()->SetText(FText::FromString(Toast));
  }
  if (ProblemLine.IsValid() && Flow.IsValid()) {
    if (Flow->IsInputBlocked()) {
      ProblemLine.Pin()->SetText(FText::FromString(
          TEXT("INPUT BLOCKED - critical fields invalid: ") +
          FString::Join(Flow->GetCriticalProblems(), TEXT("; "))));
    } else {
      FString Reason;
      if (Flow->CanIssueGameplayCommand(Reason)) {
        ProblemLine.Pin()->SetText(FText::FromString(TEXT("input allowed")));
      } else {
        ProblemLine.Pin()->SetText(FText::FromString(TEXT("command gate: ") + Reason));
      }
    }
  }
  if (TraceBox.IsValid()) {
    TraceBox->ClearChildren();
    for (const FString& Line : TraceLines) {
      TraceBox->AddSlot().AutoHeight()
          [SNew(STextBlock).Text(FText::FromString(Line))
               .Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
               .ColorAndOpacity(FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f)))];
    }
  }
}

// ---- ART-004 stage 3 T2.2: art HUD, zoom input and QA-010 traces -----------
//
// Everything below is active only on a live art board
// (BoardActor->IsArtActive(), i.e. -ArtPreview on a board with a profile in
// Config/ArtBoards/S08ArtBoardProfiles.json - Cobble 5x6 or a T3.2 fixture);
// the grey S08/S09 paths never build a plate or an icon. Colors that a pixel
// gate may look for are sRGB bytes through FLinearColor(FColor(...)) (memory
// ue-pipeline-traps 9): SColorBlock/SBorder tints are linear and the back
// buffer converts back, so the PNG carries exactly these bytes.

namespace {
// W4-C: the plate colors, fonts and sizes are the Style tokens of
// S08ArtHudStyle.h (FS08ArtHudPlateStyle); the widgets are S08ArtHudViews.h.

// W4-C: the view the viewer sees (alternate mode: the active pair member).
int32 S08ShownViewIndex(const FS08ArtHudRuntime& ArtHud, int32 Num) {
  const bool bAlternate = static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate;
  return bAlternate ? FMath::Clamp(ArtHud.ActiveView, 0, FMath::Max(0, Num - 1)) : 0;
}

// Gap between two screen rectangles (0 when they touch or overlap).
float S08RectGap(const FS08ScreenRect& A, const FS08ScreenRect& B) {
  const float Dx = FMath::Max(0.0f, FMath::Max(A.X0 - B.X1, B.X0 - A.X1));
  const float Dy = FMath::Max(0.0f, FMath::Max(A.Y0 - B.Y1, B.Y0 - A.Y1));
  return FMath::Sqrt(Dx * Dx + Dy * Dy);
}
}  // namespace

void AS08FlowGameMode::BuildArtHudWidgets(const TSharedRef<SConstraintCanvas>& Canvas) {
  // BuildUi runs before BeginPlay opens the trace file: these lines are kept
  // in ArtHud.PendingTrace and flushed right after FS08Trace::Open().
  const TCHAR* Cmd = FCommandLine::Get();
  const bool bArtPreview = FParse::Param(Cmd, TEXT("ArtPreview"));
  ArtHud.bEnabled = bArtPreview && !FParse::Param(Cmd, TEXT("ArtPreviewNoPlate"));
  ArtHud.bIconProbe = bArtPreview && FParse::Param(Cmd, TEXT("ArtPreviewIconProbe"));
  FString SizeText;
  FParse::Value(Cmd, TEXT("ArtPreviewIconSize="), SizeText);
  ArtHud.IconSize = S08ParseIconSize(SizeText, 32);
  // W5b-R D-2 / D-1 flags.
  {
    FString ModeText;
    FParse::Value(Cmd, TEXT("S08TeamColorMode="), ModeText);
    ES08TeamColorMode Mode = ES08TeamColorMode::Absolute;
    if (!S08ParseTeamColorMode(ModeText, Mode)) {
      ArtHud.PendingTrace.Add(FString::Printf(
          TEXT("HUD team colour mode '%s' refused (absolute/relative only) - using absolute"), *ModeText));
      Mode = ES08TeamColorMode::Absolute;
    }
    ArtHud.TeamColorMode = static_cast<uint8>(Mode);
    FString Names;
    FParse::Value(Cmd, TEXT("ArtPreviewTagNames="), Names);
    ArtHud.bTagNamesAll = Names.Equals(TEXT("all"), ESearchCase::IgnoreCase);
  }
  if (ArtHud.IconSize == 0) {
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD icon size '%s' refused (24/32/48 only) - using 32"), *SizeText));
    ArtHud.IconSize = 32;
  }
  // Exact-size combat icon textures (no mips, UI group): a 1254 px concept
  // drawn at 24 px without mips aliases badly, so each size is its own
  // pre-filtered texture (tools/art/art004_hud_icon_import.py).
  if (bArtPreview) {
    // W5b-R D-5: the opaque target token (dark body, light rim); the T2.2 concept size stays the fallback.
    const FString TokenPath = FString::Printf(TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_Action_AttackToken_%d"),
                                              ArtHud.IconSize);
    const FString ConceptPath = FString::Printf(TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_Action_Attack_%d"),
                                                ArtHud.IconSize);
    UTexture2D* Texture = S08LegacyRender() ? nullptr : LoadObject<UTexture2D>(nullptr, *TokenPath);
    const FString Path = Texture ? TokenPath : ConceptPath;
    if (!Texture) Texture = LoadObject<UTexture2D>(nullptr, *ConceptPath);
    ArtHud.IconTexturePath = Texture ? Path : FString(TEXT("none"));
    // W5b-R D-3: team shape chips (circle P1 / hexagon P2), 12 px exact-size, tinted by the chip colour.
    bool bChips = !S08LegacyRender();
    for (int32 I = 0; I < 2 && bChips; ++I) {
      UTexture2D* Chip = LoadObject<UTexture2D>(nullptr, I == 0
          ? TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_Circle_12")
          : TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_Hex_12"));
      if (!Chip) {
        bChips = false;
        break;
      }
      ArtHudAssets.Add(Chip);
      FSlateBrush& Brush = I == 0 ? ArtHud.ChipCircleBrush : ArtHud.ChipHexBrush;
      Brush.SetResourceObject(Chip);
      Brush.ImageSize = FVector2D(12.0, 12.0);
      Brush.DrawAs = ESlateBrushDrawType::Image;
      Brush.Tiling = ESlateBrushTileType::NoTile;
    }
    ArtHud.bChipBrushes = bChips;
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD team chips ready=%d mode=%s tagNames=%s"), bChips ? 1 : 0,
                                            S08TeamColorModeName(static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode)),
                                            ArtHud.bTagNamesAll ? TEXT("all") : TEXT("rule")));
    ArtHud.bIconTextureReady = Texture != nullptr;
    if (Texture) {
      ArtHudAssets.Add(Texture);
      ArtHud.IconBrush.SetResourceObject(Texture);
      ArtHud.IconBrush.ImageSize = FVector2D(ArtHud.IconSize, ArtHud.IconSize);
      ArtHud.IconBrush.DrawAs = ESlateBrushDrawType::Image;
      ArtHud.IconBrush.Tiling = ESlateBrushTileType::NoTile;
    }
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD icon texture size=%d ready=%d path=%s texture=%dx%d probe=%d plate=%d"),
                                     ArtHud.IconSize, Texture ? 1 : 0, *Path,
                                     Texture ? Texture->GetSizeX() : 0, Texture ? Texture->GetSizeY() : 0,
                                     ArtHud.bIconProbe ? 1 : 0, ArtHud.bEnabled ? 1 : 0));
    FString PlanText;
    if (FParse::Value(Cmd, TEXT("ArtPreviewInputPlan="), PlanText) && !PlanText.IsEmpty()) {
      FString Error;
      if (S08ParseInputPlan(PlanText, ArtHud.Plan, Error)) {
        // BuildUi runs before BeginPlay parses -ArtPreviewShotAfter: read it here.
        float ShotAfter = -1.0f;
        FParse::Value(Cmd, TEXT("ArtPreviewShotAfter="), ShotAfter);
        float After = ShotAfter >= 0.0f ? ShotAfter + 1.5f : 30.0f;
        FParse::Value(Cmd, TEXT("ArtPreviewInputAfter="), After);
        float StepSeconds = 0.35f;
        FParse::Value(Cmd, TEXT("ArtPreviewInputStep="), StepSeconds);
        ArtHud.PlanStartAt = After;
        ArtHud.PlanStepSeconds = FMath::Clamp(StepSeconds, 0.05f, 5.0f);
        ArtHud.PendingTrace.Add(FString::Printf(TEXT("INPUT plan src=flag steps=%d after=%.2f step=%.2f plan=%s"),
                                         ArtHud.Plan.Num(), ArtHud.PlanStartAt, ArtHud.PlanStepSeconds,
                                         *PlanText));
      } else {
        ArtHud.PendingTrace.Add(FString::Printf(TEXT("INPUT plan src=flag REFUSED: %s"), *Error));
      }
    }
  }

  // ---- W4-C hybrid HUD: views (S08ArtHudViews.h). -ArtHudImpl=umg (default:
  // the WBP children of the UMG widget classes, else their code default tree)
  // | slate (the T2.2 Slate widgets, transitional) | compare (UMG shown + a
  // Slate twin at render opacity 0 in the same slot geometry; both traced).
  FString ImplText;
  FParse::Value(Cmd, TEXT("ArtHudImpl="), ImplText);
  ES08ArtHudImpl Impl = ES08ArtHudImpl::Umg;
  if (!S08ParseArtHudImpl(ImplText, Impl)) {
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD art impl '%s' refused (umg/slate/compare only) - using umg"),
                                            *ImplText));
    Impl = ES08ArtHudImpl::Umg;
  }
  ArtHud.Impl = static_cast<uint8>(Impl);
  ArtHud.bTextTableReady = S08ArtHudText::EnsureTable();
  // The plate and the icon exist only on the -ArtPreview board (bEnabled and
  // the icon both require it); other runs (S09/S10 probes) get no art layer.
  if (!bArtPreview) return;

  const bool bUmg = Impl != ES08ArtHudImpl::Slate;
  const bool bSlate = Impl != ES08ArtHudImpl::Umg;
  const bool bTwinSlate = Impl == ES08ArtHudImpl::Compare;
  if (Impl == ES08ArtHudImpl::Alternate) {
    // Same-process A/B: starts after the evidence shot (-ArtPreviewShotAfter
    // + 4 s: no screenshot hitch or camera tween inside a bucket), swaps every
    // -ArtHudAlternateSeconds (default 3); -ArtHudAlternateFirst=slate flips
    // the order so runs can balance it.
    FParse::Value(Cmd, TEXT("ArtHudAlternateSeconds="), ArtHud.AlternateSeconds);
    ArtHud.AlternateSeconds = FMath::Clamp(ArtHud.AlternateSeconds, 1.0f, 60.0f);
    float ShotAfter = -1.0f;
    FParse::Value(Cmd, TEXT("ArtPreviewShotAfter="), ShotAfter);
    ArtHud.AlternateStartAt = ShotAfter >= 0.0f ? ShotAfter + 4.0f : 0.0f;
    FParse::Value(Cmd, TEXT("ArtHudAlternateStart="), ArtHud.AlternateStartAt);
    FString First;
    FParse::Value(Cmd, TEXT("ArtHudAlternateFirst="), First);
    ArtHud.AlternateFirst = First.Equals(TEXT("slate"), ESearchCase::IgnoreCase) ? 1 : 0;
    ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD alternate config periodS=%.1f startAt=%.1f first=%s"),
                                            ArtHud.AlternateSeconds, ArtHud.AlternateStartAt,
                                            ArtHud.AlternateFirst ? TEXT("slate") : TEXT("umg")));
  }
  UWorld* World = GetWorld();
  auto AddPlate = [&](const TSharedRef<IS08ArtPlateView>& View, bool bTwin) {
    const FVector2D Size = View->SizeSu();
    Canvas->AddSlot()
        .Anchors(FAnchors(0.0f, 0.0f))
        .Alignment(FVector2D(0.0f, 0.0f))
        .AutoSize(false)
        .Offset(FMargin(0.0f, 0.0f, Size.X, Size.Y))
        .Expose(View->Slot)[View->GetRoot()];
    View->SetShown(false);
    View->SetTwin(bTwin);
    if (ArtHud.bChipBrushes) View->SetTeamShapeBrushes(ArtHud.ChipCircleBrush, ArtHud.ChipHexBrush);
    ArtHud.PlateViews.Add(View);
  };
  auto AddIcon = [&](const TSharedRef<IS08ArtIconView>& View, bool bTwin) {
    Canvas->AddSlot()
        .Anchors(FAnchors(0.0f, 0.0f))
        .Alignment(FVector2D(0.0f, 0.0f))
        .AutoSize(false)
        .Offset(FMargin(0.0f, 0.0f, ArtHud.IconSize, ArtHud.IconSize))
        .Expose(View->Slot)[View->GetRoot()];
    View->SetIconBrush(ArtHud.IconBrush);
    View->SetShown(false);
    View->SetTwin(bTwin);
    ArtHud.IconViews.Add(View);
  };
  auto WidgetLine = [this](const TCHAR* What, UClass* Class, const TCHAR* Source, bool bParts,
                           const FString& Missing, bool bCodeDefault) {
    ArtHud.PendingTrace.Add(FString::Printf(
        TEXT("HUD art widget %s impl=umg source=%s class=%s parts=%d missing=%s codeDefaultTree=%d"), What, Source,
        Class ? *Class->GetPathName() : TEXT("none"), bParts ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing,
        bCodeDefault ? 1 : 0));
  };
  // W5b-R D-1: screen tags FIRST (they paint under the plate, the icon and the damage number).
  if (World && !S08LegacyRender()) {
    UClass* TagClass = S08LoadArtHudWidgetClass(US08ArtTagWidget::WidgetBlueprintPath, US08ArtTagWidget::StaticClass());
    UClass* TagUse = TagClass ? TagClass : US08ArtTagWidget::StaticClass();
    int32 Made = 0;
    FString MissingAll;
    bool bCodeDefault = false;
    for (int32 I = 0; I < 8; ++I) {
      US08ArtTagWidget* Tag = CreateWidget<US08ArtTagWidget>(World, TagUse);
      if (!Tag) break;
      FString Missing;
      if (!Tag->HasAllParts(&Missing)) {
        MissingAll = Missing;
        break;
      }
      bCodeDefault = Tag->UsesCodeDefaultTree();
      ArtHudWidgets.Add(Tag);
      if (ArtHud.bChipBrushes) Tag->SetTeamShapeBrushes(ArtHud.ChipCircleBrush, ArtHud.ChipHexBrush);
      Tag->SetVisibility(ESlateVisibility::Collapsed);
      FS08ArtHudRuntime::FTagSlot TagSlot;
      TagSlot.Widget = Tag;
      Canvas->AddSlot()
          .Anchors(FAnchors(0.0f, 0.0f))
          .Alignment(FVector2D(0.0f, 0.0f))
          .AutoSize(true)
          .Offset(FMargin(0.0f, 0.0f, 0.0f, 0.0f))
          .Expose(TagSlot.Slot)[Tag->TakeWidget()];
      ArtHud.Tags.Add(TagSlot);
      ++Made;
    }
    ArtHud.bTagsEnabled = Made == 8;
    ArtHud.PendingTrace.Add(FString::Printf(
        TEXT("HUD art widget tag impl=umg source=%s class=%s count=%d missing=%s codeDefaultTree=%d"),
        TagClass ? US08ArtTagWidget::WidgetBlueprintPath : TEXT("code-default"), *TagUse->GetPathName(), Made,
        MissingAll.IsEmpty() ? TEXT("-") : *MissingAll, bCodeDefault ? 1 : 0));
  }
  bool bUmgPlate = false;
  bool bUmgIcon = false;
  if (bUmg && World) {
    // Plate: the designer's WBP when it is cooked, else the class's code
    // default tree (identical to the Slate plate by construction and test).
    UClass* PlateClass = S08LoadArtHudWidgetClass(US08ArtPlateWidget::WidgetBlueprintPath,
                                                  US08ArtPlateWidget::StaticClass());
    UClass* PlateUse = PlateClass ? PlateClass : US08ArtPlateWidget::StaticClass();
    if (US08ArtPlateWidget* Plate = CreateWidget<US08ArtPlateWidget>(World, PlateUse)) {
      FString Missing;
      const bool bParts = Plate->HasAllParts(&Missing);
      const TCHAR* Source = PlateClass ? US08ArtPlateWidget::WidgetBlueprintPath : TEXT("code-default");
      WidgetLine(TEXT("plate"), PlateUse, Source, bParts, Missing, Plate->UsesCodeDefaultTree());
      if (bParts) {
        ArtHudWidgets.Add(Plate);
        AddPlate(S08MakeUmgPlateView(*Plate, Source), false);
        bUmgPlate = true;
      }
    }
    UClass* IconClass = S08LoadArtHudWidgetClass(US08ArtIconWidget::WidgetBlueprintPath,
                                                 US08ArtIconWidget::StaticClass());
    UClass* IconUse = IconClass ? IconClass : US08ArtIconWidget::StaticClass();
    if (US08ArtIconWidget* IconWidget = CreateWidget<US08ArtIconWidget>(World, IconUse)) {
      FString Missing;
      const bool bParts = IconWidget->HasAllParts(&Missing);
      const TCHAR* Source = IconClass ? US08ArtIconWidget::WidgetBlueprintPath : TEXT("code-default");
      WidgetLine(TEXT("icon"), IconUse, Source, bParts, Missing, IconWidget->UsesCodeDefaultTree());
      if (bParts) {
        ArtHudWidgets.Add(IconWidget);
        AddIcon(S08MakeUmgIconView(*IconWidget, Source), false);
        bUmgIcon = true;
      }
    }
  }
  // Slate: the transitional path, the compare twin, and the fallback when a
  // UMG widget could not be created (traced above with parts=0).
  if (bSlate || !bUmgPlate) {
    AddPlate(S08MakeSlatePlateView(FS08ArtHudPlateStyle()), bUmgPlate && bTwinSlate);
  }
  if (bSlate || !bUmgIcon) {
    AddIcon(S08MakeSlateIconView(), bUmgIcon && bTwinSlate);
  }
  // W5b-R D-1: the damage number LAST (above the tags, the plate and the icon).
  if (World && ArtHud.bTagsEnabled) {
    UClass* DamageClass =
        S08LoadArtHudWidgetClass(US08ArtDamageWidget::WidgetBlueprintPath, US08ArtDamageWidget::StaticClass());
    UClass* DamageUse = DamageClass ? DamageClass : US08ArtDamageWidget::StaticClass();
    US08ArtDamageWidget* Damage = CreateWidget<US08ArtDamageWidget>(World, DamageUse);
    FString Missing;
    if (Damage && Damage->HasAllParts(&Missing)) {
      ArtHudWidgets.Add(Damage);
      Damage->SetVisibility(ESlateVisibility::Collapsed);
      ArtHud.DamageWidget = Damage;
      Canvas->AddSlot()
          .Anchors(FAnchors(0.0f, 0.0f))
          .Alignment(FVector2D(0.0f, 0.0f))
          .AutoSize(true)
          .Offset(FMargin(0.0f, 0.0f, 0.0f, 0.0f))
          .Expose(ArtHud.DamageSlot)[Damage->TakeWidget()];
    }
    ArtHud.PendingTrace.Add(FString::Printf(
        TEXT("HUD art widget damage impl=umg source=%s class=%s parts=%d missing=%s codeDefaultTree=%d"),
        DamageClass ? US08ArtDamageWidget::WidgetBlueprintPath : TEXT("code-default"), *DamageUse->GetPathName(),
        ArtHud.DamageWidget ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing,
        (Damage && Damage->UsesCodeDefaultTree()) ? 1 : 0));
  }
}

float AS08FlowGameMode::HudPixelsPerUnit() const {
  if (!HudCanvas.IsValid() || !GEngine || !GEngine->GameViewport) return 0.0f;
  FVector2D ViewportPx(0.0, 0.0);
  GEngine->GameViewport->GetViewportSize(ViewportPx);
  const FVector2D Local = HudCanvas->GetPaintSpaceGeometry().GetLocalSize();
  if (ViewportPx.X <= 0.0 || Local.X <= 0.0) return 0.0f;
  return static_cast<float>(ViewportPx.X / Local.X);
}

bool AS08FlowGameMode::WidgetViewportRect(const TSharedPtr<SWidget>& Widget, FS08ScreenRect& OutRect) const {
  OutRect = FS08ScreenRect();
  if (!Widget.IsValid() || !HudCanvas.IsValid() || !GEngine || !GEngine->GameViewport) return false;
  if (Widget->GetVisibility() == EVisibility::Collapsed) return false;
  FVector2D ViewportPx(0.0, 0.0);
  GEngine->GameViewport->GetViewportSize(ViewportPx);
  const FGeometry& CanvasGeo = HudCanvas->GetPaintSpaceGeometry();
  const FVector2D CanvasAbs = CanvasGeo.GetAbsoluteSize();
  if (CanvasAbs.X <= 0.0 || ViewportPx.X <= 0.0) return false;
  const double PxPerAbs = ViewportPx.X / CanvasAbs.X;
  const FGeometry& Geo = Widget->GetPaintSpaceGeometry();
  const FVector2D Pos = (Geo.GetAbsolutePosition() - CanvasGeo.GetAbsolutePosition()) * PxPerAbs;
  const FVector2D Size = Geo.GetAbsoluteSize() * PxPerAbs;
  OutRect = FS08ScreenRect(static_cast<float>(Pos.X), static_cast<float>(Pos.Y),
                           static_cast<float>(Pos.X + Size.X), static_cast<float>(Pos.Y + Size.Y));
  return true;
}

bool AS08FlowGameMode::ProjectToViewport(const FVector& World, FVector2D& OutScreen) const {
  const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  return PC && PC->ProjectWorldLocationToScreen(World, OutScreen, true);
}

const FS08BoardFighter* AS08FlowGameMode::FindFighter(const FString& FighterId) const {
  if (FighterId.IsEmpty()) return nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == FighterId) return &Entry;
  }
  return nullptr;
}

bool AS08FlowGameMode::FigureScreenRect(const FString& FighterId, FS08ScreenRect& OutRect) const {
  const FS08BoardFighter* Fighter = FindFighter(FighterId);
  if (!Fighter || !Fighter->IsAlive() || !BoardActor) return false;
  const AS08FighterActor* Actor = BoardActor->FindFighterActor(FighterId);
  const float Height = Actor ? Actor->GetFigureHeightUU() : 60.0f;
  // W5b-R D-3: an art figure's box includes its team ring (outer edge = the rim, 5c-B1: 28.5 uu hero / 22.23 sidekick; r3 28 / 21.84), so the plate,
  // the icon and the tags keep off the rings (T5.2: the Medusa plate touched Arthur's ring on Cobble).
  const float Radius = (Actor && Actor->HasArtFigure())
      ? (Fighter->bIsHero ? S08TeamRingSpec::HeroRectRadiusUU : S08TeamRingSpec::SidekickRectRadiusUU)
      : 30.0f;
  const FVector Base = BoardModel.CellToWorld(Fighter->X, Fighter->Y);
  TArray<FVector2D> Points;
  for (const float Z : {0.0f, Height}) {
    for (const float Dx : {-Radius, Radius}) {
      for (const float Dy : {-Radius, Radius}) {
        FVector2D Screen;
        if (!ProjectToViewport(Base + FVector(Dx, Dy, Z), Screen)) return false;
        Points.Add(Screen);
      }
    }
  }
  OutRect = FS08ScreenRect::FromPoints(Points);
  return true;
}

void AS08FlowGameMode::CurrentSelection(FString& OutFighterId, TSet<uint64>& OutLegalCells) const {
  OutFighterId.Reset();
  OutLegalCells.Reset();
  if (CommandUi.Mode == ES09CommandMode::PendingChoice &&
      (!CommandUi.PendingFighterId.IsEmpty() || CommandUi.PendingCells.Num() > 0)) {
    OutFighterId = CommandUi.PendingFighterId;
    OutLegalCells = CommandUi.PendingCells;
  } else if (CommandUi.Mode == ES09CommandMode::ManeuverDraft && !CommandUi.SelectedFighterId.IsEmpty()) {
    OutFighterId = CommandUi.SelectedFighterId;
    OutLegalCells = CommandUi.ReachableCells;
  } else if (!SelectedFighterId.IsEmpty()) {
    OutFighterId = SelectedFighterId;
    OutLegalCells = ReachableCells;
  }
}

TArray<FS08CellQuad> AS08FlowGameMode::ProjectCells(const TArray<FIntPoint>& Cells) const {
  TArray<FS08CellQuad> Out;
  const float Half = FS08BoardModel::CellSizeUU * 0.5f;
  for (const FIntPoint& Cell : Cells) {
    const FVector C = BoardModel.CellToWorld(Cell.X, Cell.Y);
    FS08CellQuad Quad;
    Quad.Cell = Cell;
    bool bOk = true;
    for (const FVector2D& Corner : {FVector2D(-Half, -Half), FVector2D(Half, -Half), FVector2D(Half, Half),
                                    FVector2D(-Half, Half)}) {
      FVector2D Screen;
      if (!ProjectToViewport(C + FVector(Corner.X, Corner.Y, 0.0f), Screen)) {
        bOk = false;
        break;
      }
      Quad.Screen.Add(Screen);
    }
    if (bOk) Out.Add(MoveTemp(Quad));
  }
  return Out;
}

FString AS08FlowGameMode::PlateFighterIdNow() const {
  FString Selected;
  TSet<uint64> Legal;
  CurrentSelection(Selected, Legal);
  if (!Selected.IsEmpty()) return Selected;
  return ArtHud.HoveredFighterId;
}

void AS08FlowGameMode::ApplyWheel(int32 Direction, ES08InputSource Source) {
  if (!CameraZoom.IsReady()) return;
  const TCHAR* Dir = Direction > 0 ? TEXT("in") : TEXT("out");
  const FS08ZoomStep Step = CameraZoom.Wheel(Direction);
  FS08Trace::Write(FString::Printf(TEXT("INPUT wheel dir=%s src=%s"), Dir, S08InputSourceName(Source)));
  FS08Trace::Write(FString::Printf(
      TEXT("CAMERA wheel dir=%s src=%s from=%.1f to=%.1f requested=%.1f zoom=%.2f clamp=%d limit=%s animMs=%.0f follow=%d"),
      Dir, S08InputSourceName(Source), Step.From, Step.To, Step.Requested, CameraZoom.ZoomOf(Step.To),
      Step.bClamped ? 1 : 0, S08ZoomLimitName(Step.Limit), Step.Seconds * 1000.0f,
      CameraZoom.WantsFollow() ? 1 : 0));
  if (Step.bClamped) {
    FS08Trace::Write(FString::Printf(
        TEXT("CAMERA clamp limit=%s src=%s dist=%.1f requested=%.1f zoom=%.2f range=%.2f-%.2f"),
        S08ZoomLimitName(Step.Limit), S08InputSourceName(Source), Step.To, Step.Requested,
        CameraZoom.ZoomOf(Step.To), CameraZoom.ZoomOf(CameraZoom.MaxDistance()),
        CameraZoom.ZoomOf(CameraZoom.MinDistance())));
  }
}

void AS08FlowGameMode::ApplySpace(ES08InputSource Source) {
  if (!CameraZoom.IsReady()) return;
  const FS08ZoomStep Step = CameraZoom.ReturnToOverview();
  FS08Trace::Write(FString::Printf(TEXT("INPUT space src=%s"), S08InputSourceName(Source)));
  FS08Trace::Write(FString::Printf(
      TEXT("CAMERA space src=%s from=%.1f to=%.1f zoom=%.2f animMs=%.0f follow=%d"),
      S08InputSourceName(Source), Step.From, Step.To, CameraZoom.ZoomOf(Step.To), Step.Seconds * 1000.0f,
      CameraZoom.WantsFollow() ? 1 : 0));
}

void AS08FlowGameMode::TraceOsClick(const FKey& Button) {
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor) return;
  float MouseX = -1.0f, MouseY = -1.0f;
  const bool bMouse = PC->GetMousePosition(MouseX, MouseY);
  FHitResult Hit;
  const bool bHit = PC->GetHitResultUnderCursor(ECC_Visibility, false, Hit);
  const AS08FighterActor* FighterActor = bHit ? Cast<AS08FighterActor>(Hit.GetActor()) : nullptr;
  int32 CellX = -1, CellY = -1;
  const bool bCell = bHit && !FighterActor && BoardActor->WorldToCell(Hit.ImpactPoint, CellX, CellY);
  FS08Trace::Write(FString::Printf(
      TEXT("INPUT click button=%s src=os screen=(%.0f,%.0f) mouse=%d hit=%d actor=%s comp=%s fighter=%s cell=(%d,%d) mode=%d dispatch=1"),
      Button == EKeys::LeftMouseButton ? TEXT("left") : TEXT("right"), MouseX, MouseY, bMouse ? 1 : 0,
      bHit ? 1 : 0, Hit.GetActor() ? *Hit.GetActor()->GetName() : TEXT("none"),
      Hit.GetComponent() ? *Hit.GetComponent()->GetName() : TEXT("none"),
      FighterActor ? *FighterActor->GetFighterId() : TEXT("none"), bCell ? CellX : -1, bCell ? CellY : -1,
      static_cast<int32>(CommandUi.Mode)));
}

void AS08FlowGameMode::UpdateHover() {
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor || !BoardActor->IsArtActive()) return;
  float X = 0.0f, Y = 0.0f;
  if (!PC->GetMousePosition(X, Y)) return;
  // Offscreen evidence clients never move the OS cursor: only a cursor that
  // actually moved counts as hover, so K1/K2 frames stay deterministic.
  if (ArtHud.FirstMouse.X < 0.0) ArtHud.FirstMouse = FVector2D(X, Y);
  if (!ArtHud.bMouseMoved && !FVector2D(X, Y).Equals(ArtHud.FirstMouse, 0.5)) ArtHud.bMouseMoved = true;
  if (!ArtHud.bMouseMoved) return;
  FHitResult Hit;
  FString Id;
  if (PC->GetHitResultAtScreenPosition(FVector2D(X, Y), ECC_Visibility, false, Hit)) {
    if (const AS08FighterActor* Actor = Cast<AS08FighterActor>(Hit.GetActor())) Id = Actor->GetFighterId();
  }
  if (Id != ArtHud.HoveredFighterId) {
    ArtHud.HoveredFighterId = Id;
    FS08Trace::Write(FString::Printf(TEXT("INPUT hover src=os screen=(%.0f,%.0f) fighter=%s"), X, Y,
                                     Id.IsEmpty() ? TEXT("none") : *Id));
  }
}

void AS08FlowGameMode::UpdateArtHud(float DeltaSeconds) {
  const bool bBoard = BoardActor && BoardActor->IsArtActive() && Flow.IsValid() &&
                      Flow->GetStage() == ES08Stage::Started;
  const bool bActive = ArtHud.bEnabled && bBoard && !Hud.bGameOver;
  if (bBoard && !ArtHud.bConfigTraced && CameraZoom.IsReady()) {
    ArtHud.bConfigTraced = true;
    FS08Trace::Write(FString::Printf(TEXT("HUD art layer plate=%d iconSize=%d iconTexture=%d iconProbe=%d plan=%d"),
                                     ArtHud.bEnabled ? 1 : 0, ArtHud.IconSize, ArtHud.bIconTextureReady ? 1 : 0,
                                     ArtHud.bIconProbe ? 1 : 0, ArtHud.Plan.Num()));
    // W4-C: which views draw the layer (shown first; compare adds the twin).
    TArray<FString> PlateViews, IconViews;
    for (const TSharedPtr<IS08ArtPlateView>& View : ArtHud.PlateViews) {
      PlateViews.Add(FString::Printf(TEXT("%s%s:%s"), View->ImplName(), View->bTwin ? TEXT("(twin)") : TEXT(""),
                                     *View->Source()));
    }
    for (const TSharedPtr<IS08ArtIconView>& View : ArtHud.IconViews) {
      IconViews.Add(FString::Printf(TEXT("%s%s:%s"), View->ImplName(), View->bTwin ? TEXT("(twin)") : TEXT(""),
                                    *View->Source()));
    }
    const TArray<FString> MissingKeys = S08ArtHudText::MissingKeys();
    FS08Trace::Write(FString::Printf(
        TEXT("HUD art impl=%s plateViews=%s iconViews=%s textTable=%s entries=%d missingKeys=%d%s%s"),
        S08ArtHudImplName(static_cast<ES08ArtHudImpl>(ArtHud.Impl)),
        PlateViews.Num() ? *FString::Join(PlateViews, TEXT(",")) : TEXT("none"),
        IconViews.Num() ? *FString::Join(IconViews, TEXT(",")) : TEXT("none"), *S08ArtHudText::TableId.ToString(),
        S08ArtHudText::NumEntries(), MissingKeys.Num(), MissingKeys.Num() ? TEXT(" missing=") : TEXT(""),
        *FString::Join(MissingKeys, TEXT(","))));
  }
  if (bBoard) {
    RunArtPreviewInputPlan();
    UpdateHover();
  }
  UpdatePlate(bActive);
  UpdateCombatIcon(bActive);
  // W4-C alternate mode: one view pair visible at a time, swapped every
  // AlternateSeconds while the plate is on screen (the same-process A/B of
  // the game-thread cost; PERF skips the first frames after each swap).
  ++ArtHud.FramesSinceSwap;
  if (static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate && ArtHud.bPlateVisible &&
      ArtHud.PlateViews.Num() > 1) {
    const bool bStart = !ArtHud.bAlternateStarted && Elapsed >= ArtHud.AlternateStartAt;
    if (bStart || (ArtHud.bAlternateStarted && Elapsed >= ArtHud.NextSwapAt)) {
      // Close the period that just ended: one line per period, so the A/B can
      // be paired period by period (robust to bursts of external CPU load).
      if (ArtHud.bAlternateStarted && GS08ArtProbe.PeriodGameMs.Num() > 0) {
        FS08Trace::Write(FString::Printf(
            TEXT("HUD alternate period=%d impl=%s frames=%d gameAvg=%.3f gameP50=%.3f gameP95=%.3f gpuP95=%.3f"),
            ArtHud.Swaps, ArtHud.PlateViews[ArtHud.ActiveView]->ImplName(), GS08ArtProbe.PeriodGameMs.Num(),
            S08PerfMean(GS08ArtProbe.PeriodGameMs), S08PerfPercentile(GS08ArtProbe.PeriodGameMs, 0.50f),
            S08PerfPercentile(GS08ArtProbe.PeriodGameMs, 0.95f), S08PerfPercentile(GS08ArtProbe.PeriodGpuMs, 0.95f)));
      }
      GS08ArtProbe.PeriodGameMs.Reset();
      GS08ArtProbe.PeriodGpuMs.Reset();
      ArtHud.ActiveView = bStart ? ArtHud.AlternateFirst : 1 - ArtHud.ActiveView;
      ArtHud.bAlternateStarted = true;
      ArtHud.NextSwapAt = Elapsed + ArtHud.AlternateSeconds;
      ArtHud.FramesSinceSwap = 0;
      ++ArtHud.Swaps;
      for (int32 Index = 0; Index < ArtHud.PlateViews.Num(); ++Index) {
        ArtHud.PlateViews[Index]->SetShown(ArtHud.IsViewShown(Index, true));
      }
      for (int32 Index = 0; Index < ArtHud.IconViews.Num() && ArtHud.bIconVisible; ++Index) {
        ArtHud.IconViews[Index]->SetShown(ArtHud.IsViewShown(Index, true));
      }
      ArtHud.PlateStableFrames = 0;  // the newly shown view paints next frame
      FS08Trace::Write(FString::Printf(TEXT("HUD alternate swap=%d active=%s elapsed=%.2f"), ArtHud.Swaps,
                                       ArtHud.PlateViews[ArtHud.ActiveView]->ImplName(), Elapsed));
    }
  }
  // W4-C compare mode: besides the SHOT blocks, a same-frame parity sample of
  // both views every 0.5 s while the plate stands still (camera tweens and
  // flag input plans move it between samples).
  if (static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Compare && ArtHud.bPlateVisible &&
      ArtHud.PlateStableFrames >= 2 && Elapsed >= ArtHud.NextCompareSampleAt) {
    ArtHud.NextCompareSampleAt = Elapsed + 0.5f;
    ++ArtHud.CompareSamples;
    WriteArtHudWidgetLines(FString::Printf(TEXT("HUD sample=%d "), ArtHud.CompareSamples));
  }
  if (BoardActor) {
    BoardActor->SetLabelPresentation(bActive && ArtHud.bPlateVisible ? ArtHud.PlateFighterId : FString());
    // W5b-R D-1: the screen tag layer replaces the world TextRender labels / damage text on the art board.
    BoardActor->SetScreenLabelMode(ArtHud.bTagsEnabled && bBoard);
  }
}

void AS08FlowGameMode::UpdateCombatIcon(bool bActive) {
  if (ArtHud.IconViews.Num() == 0) return;
  FString Target;
  FString Source;
  if (bActive && BoardActor) {
    if (!BoardActor->GetCombatTargetId().IsEmpty()) {
      Target = BoardActor->GetCombatTargetId();
      Source = TEXT("combat");
    } else if (ArtHud.bIconProbe) {
      // Flag probe (src=flag): the nearest living enemy of the viewer's hero
      // carries the icon so K2 frames can measure it at 24/32/48 px without a
      // combat. It is not a server state and never sends a command.
      const FS08BoardFighter* OwnHero = nullptr;
      for (const FS08BoardFighter& F : Fighters) {
        if (F.OwnerId == Flow->GetUserId() && F.bIsHero && F.IsAlive()) OwnHero = &F;
      }
      int32 BestDist = MAX_int32;
      for (const FS08BoardFighter& F : Fighters) {
        if (!F.IsAlive() || F.OwnerId == Flow->GetUserId()) continue;
        // Spaces between (links on an original map, manhattan on a grid); an
        // unreachable enemy still ranks, after every reachable one.
        const int32 Dist = OwnHero ? FMath::Min(BoardModel.GraphDistance(FIntPoint(OwnHero->X, OwnHero->Y),
                                                                         FIntPoint(F.X, F.Y)),
                                                MAX_int32 - 1)
                                   : 0;
        if (Dist < BestDist) {
          BestDist = Dist;
          Target = F.Id;
        }
      }
      Source = TEXT("flag");
    }
  }
  if (BoardActor) BoardActor->SetScreenIconMode(bActive && ArtHud.bIconTextureReady);
  const FString PrevIconFighter = ArtHud.IconFighterId;
  UpdateBoardLabels(bActive, Target, Source);
  if (!Target.IsEmpty() && Source == TEXT("flag") && PrevIconFighter != Target && ArtHud.bIconVisible) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW icon probe src=flag target=%s size=%d"), *Target,
                                     ArtHud.IconSize));
  }
}

void AS08FlowGameMode::UpdatePlate(bool bActive) {
  if (ArtHud.PlateViews.Num() == 0) return;
  const FString Id = bActive ? PlateFighterIdNow() : FString();
  const FS08BoardFighter* Fighter = FindFighter(Id);
  const float Ppu = HudPixelsPerUnit();
  FS08ScreenRect Anchor;
  if (!Fighter || !Fighter->IsAlive() || Ppu <= 0.0f || !FigureScreenRect(Id, Anchor)) {
    if (ArtHud.bPlateVisible) {
      for (const TSharedPtr<IS08ArtPlateView>& View : ArtHud.PlateViews) View->SetShown(false);
      ArtHud.bPlateVisible = false;
      FS08Trace::Write(FString::Printf(TEXT("PLATE hidden fighter=%s"), *ArtHud.PlateFighterId));
      ArtHud.PlateFighterId.Reset();
      ArtHud.PlateLastTraced.Reset();
      ArtHud.PlateSignature.Reset();
    }
    ArtHud.PlateStableFrames = 0;
    return;
  }
  // ---- content (rebuilt only when the data changes)
  const bool bOwn = Flow.IsValid() && Fighter->OwnerId == Flow->GetUserId();
  const FString AttackerId = CommandUi.Combat.bPresent ? CommandUi.Combat.AttackerId : CommandUi.AttackAttackerId;
  const FString TargetId = BoardActor ? BoardActor->GetCombatTargetId() : FString();
  const TArray<FString> Statuses = S08PlateStatuses(Fighter->bIsHero, bOwn, Fighter->AttackType,
                                                    Fighter->Id == AttackerId, Fighter->Id == TargetId,
                                                    Fighter->Effects);
  const FString PlateStatusLine = FString::Join(Statuses, TEXT("  |  "));
  const ES08TeamSlot PlateTeam = BoardActor ? BoardActor->TeamOfFighter(*Fighter) : ES08TeamSlot::P1;
  const ES08TeamSlot PlateLook =
      S08TeamLook(PlateTeam, bOwn, static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode));
  const FString ContentKey = FString::Printf(TEXT("%s|%s|%d|%d|%d|%s|%d"), *Fighter->Id, *Fighter->Label,
                                             Fighter->Health, Fighter->MaxHealth, bOwn ? 1 : 0, *PlateStatusLine,
                                             static_cast<int32>(PlateLook));
  if (ContentKey != ArtHud.PlateContentKey) {
    ArtHud.PlateContentKey = ContentKey;
    // W4-C: the views show string-table text (S08ArtHudText); the trace
    // below keeps the English codes byte for byte.
    FS08PlateTexts Texts =
        S08ArtHudText::PlateTexts(Fighter->Label, Fighter->Health, Fighter->MaxHealth, bOwn, Statuses);
    Texts.TeamSlot = PlateLook == ES08TeamSlot::P1 ? 0 : 1;
    for (const TSharedPtr<IS08ArtPlateView>& View : ArtHud.PlateViews) View->ApplyTexts(Texts);
    FS08Trace::Write(FString::Printf(
        TEXT("HUD plate content fighter=%s name=%s hp=%d/%d team=%s statuses=%s teamSlot=%s look=%s shape=%s chip=%s"),
        *Fighter->Id, *Fighter->Label, Fighter->Health, Fighter->MaxHealth, bOwn ? TEXT("own") : TEXT("enemy"),
        *PlateStatusLine, S08TeamSlotName(PlateTeam), S08TeamSlotName(PlateLook), S08TeamShapeName(PlateLook),
        PlateLook == ES08TeamSlot::P1 ? S08TeamPalette::P1ScreenHex : S08TeamPalette::P2ScreenHex));
  }
  // ---- placement: never over a destination cell of the current selection
  FString SelectedId;
  TSet<uint64> Legal;
  CurrentSelection(SelectedId, Legal);
  FIntPoint OwnCell(-1, -1);
  if (const FS08BoardFighter* Selected = FindFighter(SelectedId)) OwnCell = FIntPoint(Selected->X, Selected->Y);
  const TArray<FIntPoint> Destinations = S08ArtHud::DestinationCells(Legal, OwnCell);
  S08ArtHud::FPlacementInput In;
  FVector2D ViewportPx(0.0, 0.0);
  GEngine->GameViewport->GetViewportSize(ViewportPx);
  In.Viewport = ViewportPx;
  // Plate size from the shown view's Style tokens (a WBP may change it).
  const FVector2D PlateSizeSu = ArtHud.PlateViews[0]->SizeSu();
  In.PlateSize = FVector2D(FMath::RoundToFloat(PlateSizeSu.X * Ppu), FMath::RoundToFloat(PlateSizeSu.Y * Ppu));
  In.Anchor = Anchor;
  In.Forbidden = ProjectCells(Destinations);
  // Soft obstacles: every visible figure incl. the owner (W5b-R: the box includes the team ring) and the HUD panels.
  // W5b-R D-1: the screen tags, the icon and the damage number are placed AFTER the plate and avoid it as a hard
  // obstacle (a plate that also avoided them would chase them frame to frame).
  for (const FS08BoardFighter& F : Fighters) {
    FS08ScreenRect R;
    if (F.IsAlive() && FigureScreenRect(F.Id, R)) {
      In.Soft.Add(R);
      if (F.Id != Id) In.BindOthers.Add(R);
    }
  }
  In.BindTarget = Anchor;  // W5b-R: the plate reads as its owner's (rect gap to the owner < gap to any other figure)
  if (!ArtHud.bTagsEnabled) {
    // pre-W5b behaviour (-S08LegacyRender): world labels, the icon and live damage numbers are soft obstacles too
    for (const FS08BoardFighter& F : Fighters) {
      const AS08FighterActor* Actor = BoardActor ? BoardActor->FindFighterActor(F.Id) : nullptr;
      FBox Box;
      if (Actor && F.Id != Id && Actor->GetVisibleLabelBox(Box)) {
        TArray<FVector2D> Corners;
        for (int32 C = 0; C < 8; ++C) {
          FVector2D S;
          const FVector P((C & 1) ? Box.Max.X : Box.Min.X, (C & 2) ? Box.Max.Y : Box.Min.Y,
                          (C & 4) ? Box.Max.Z : Box.Min.Z);
          if (ProjectToViewport(P, S)) Corners.Add(S);
        }
        if (Corners.Num() == 8) In.Soft.Add(FS08ScreenRect::FromPoints(Corners));
      }
    }
    if (ArtHud.bIconVisible) In.Soft.Add(ArtHud.IconPlanned);
  }
  for (const TWeakPtr<SWidget>& Panel : {ArtHud.CommandPanel, ArtHud.SidePanel, ArtHud.HandPanel}) {
    FS08ScreenRect R;
    if (WidgetViewportRect(Panel.Pin(), R) && !R.IsEmpty()) In.Soft.Add(R);
  }
  // The search only reruns when an input moved by a pixel (camera tween,
  // selection, figures, HUD panels); otherwise the last placement stands.
  FString Signature = FString::Printf(TEXT("%s|%s|%.0fx%.0f|%d|"), *Id, *S08ArtHud::FormatRect(Anchor),
                                      In.PlateSize.X, In.PlateSize.Y, In.Forbidden.Num());
  for (const FS08CellQuad& Q : In.Forbidden) {
    for (const FVector2D& P : Q.Screen) Signature += FString::Printf(TEXT("%.0f,%.0f;"), P.X, P.Y);
  }
  for (const FS08ScreenRect& R : In.Soft) Signature += S08ArtHud::FormatRect(R);
  if (Signature != ArtHud.PlateSignature || !ArtHud.bPlateVisible) {
    ArtHud.PlateSignature = Signature;
    ArtHud.PlateResult = S08ArtHud::ChoosePlateRect(In);
  }
  const S08ArtHud::FPlacementResult& Result = ArtHud.PlateResult;
  const FS08ScreenRect& Rect = Result.Rect;
  const bool bMoved = !ArtHud.bPlateVisible || ArtHud.PlateFighterId != Id ||
                      !FMath::IsNearlyEqual(ArtHud.PlatePlanned.X0, Rect.X0, 0.5f) ||
                      !FMath::IsNearlyEqual(ArtHud.PlatePlanned.Y0, Rect.Y0, 0.5f);
  // Every view (compare: the Slate twin too) gets the SAME slot geometry.
  const bool bAlternate = static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate;
  for (int32 Index = 0; Index < ArtHud.PlateViews.Num(); ++Index) {
    const TSharedPtr<IS08ArtPlateView>& View = ArtHud.PlateViews[Index];
    View->Slot->SetOffset(FMargin(Rect.X0 / Ppu, Rect.Y0 / Ppu, PlateSizeSu.X, PlateSizeSu.Y));
    if (!ArtHud.bPlateVisible) View->SetShown(ArtHud.IsViewShown(Index, bAlternate));
  }
  ArtHud.bPlateVisible = true;
  ArtHud.PlateFighterId = Id;
  ArtHud.PlatePlanned = Rect;
  ArtHud.PlateAnchor = Anchor;
  ArtHud.PlateCandidate = Result.Candidate;
  ArtHud.PlateForbiddenPlanned = Result.ForbiddenOverlaps;
  ArtHud.PlateStableFrames = bMoved ? 0 : ArtHud.PlateStableFrames + 1;
  // Standalone PLATE line (qa010 accepts it as the latest state): only once
  // the camera settled and the placement changed; the exact overlap uses the
  // un-grown rect, i.e. the same rule qa010 `plate` applies.
  if (CameraZoom.IsSettled()) {
    const int32 Overlap = S08ArtHud::CountOverlaps(Rect, In.Forbidden, S08ArtHud::OverlapEpsilonPx2);
    const FString Line = FString::Printf(
        TEXT("PLATE fighter=%s bbox=%s overlapReachable=%d placement=%s ring=%d gap=%.0f selection=%s destinations=%d clean=%d softPx2=%.0f tested=%d bound=%d"),
        *Id, *S08ArtHud::FormatRect(Rect), Overlap, *Result.Candidate, Result.Ring, S08RectGap(Rect, Anchor),
        SelectedId.IsEmpty() ? TEXT("none") : *SelectedId, Destinations.Num(), Result.bClean ? 1 : 0,
        Result.SoftArea, Result.Tested, Result.bBound ? 1 : 0);
    if (Line != ArtHud.PlateLastTraced) {
      ArtHud.PlateLastTraced = Line;
      FS08Trace::Write(Line);
    }
  }
}

TMap<FString, FS08ScreenRect> AS08FlowGameMode::FigureScreenRects() const {
  TMap<FString, FS08ScreenRect> Out;
  for (const FS08BoardFighter& F : Fighters) {
    FS08ScreenRect R;
    if (F.IsAlive() && FigureScreenRect(F.Id, R)) Out.Add(F.Id, R);
  }
  return Out;
}

void AS08FlowGameMode::UpdateBoardLabels(bool bActive, const FString& IconTarget, const FString& IconSource) {
  FVector2D ViewportPx(0.0, 0.0);
  if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(ViewportPx);
  const float Ppu = HudPixelsPerUnit();
  const bool bBoard = BoardActor && BoardActor->IsArtActive() && Flow.IsValid() &&
                      Flow->GetStage() == ES08Stage::Started && Ppu > 0.0f;
  const bool bTagsActive = ArtHud.bTagsEnabled && bBoard && !Hud.bGameOver;
  // ENV-MAPS P4: map-image boards whose profile has readability.labelPlates draw the tags on the board plate (dark
  // semi-opaque rounded plate, team-colour outline) and keep a hard gap between stacked tags; grids never do.
  const bool bBoardPlates = bTagsActive && BoardActor->UsesLabelPlates();
  const float TagHardPadPx = bBoardPlates ? S08ArtHudBoardPlate::TagHardPadPx : 0.0f;
  if (static_cast<int8>(bBoardPlates ? 1 : 0) != ArtHud.BoardPlateTraced && bTagsActive) {
    ArtHud.BoardPlateTraced = bBoardPlates ? 1 : 0;
    FS08Trace::Write(FString::Printf(TEXT("HUD tags boardPlate=%d hardPadPx=%.0f profile=%s"), bBoardPlates ? 1 : 0,
                                     TagHardPadPx, *BoardActor->GetArtProfileId()));
  }
  const TMap<FString, FS08ScreenRect> Figures = bBoard ? FigureScreenRects() : TMap<FString, FS08ScreenRect>();
  TArray<FS08ScreenRect> Panels;
  for (const TWeakPtr<SWidget>& Panel : {ArtHud.CommandPanel, ArtHud.SidePanel, ArtHud.HandPanel}) {
    FS08ScreenRect R;
    if (WidgetViewportRect(Panel.Pin(), R) && !R.IsEmpty()) Panels.Add(R);
  }
  const FString ViewerId = Flow.IsValid() ? Flow->GetUserId() : FString();
  const bool bK2 = CameraZoom.IsReady() &&
                   CameraZoom.ZoomOf(CameraZoom.Current) >= CameraZoom.Config.FollowFromZoom - 0.01f;
  FString SelectedId;
  TSet<uint64> Legal;
  CurrentSelection(SelectedId, Legal);

  // ---- tag content (pushed on change only, HUD-RULES P2)
  TArray<const FS08BoardFighter*> Alive;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.IsAlive() && Figures.Contains(F.Id)) Alive.Add(&F);
  }
  FString Signature = FString::Printf(TEXT("%d|%d|%.0fx%.0f|%s|%s|%d|%d|"), bTagsActive ? 1 : 0, bActive ? 1 : 0,
                                      ViewportPx.X, ViewportPx.Y, *IconTarget, *IconSource, ArtHud.IconSize,
                                      bK2 ? 1 : 0);
  if (bBoardPlates) Signature += TEXT("plates|");
  for (int32 I = 0; I < ArtHud.Tags.Num(); ++I) {
    FS08ArtHudRuntime::FTagSlot& T = ArtHud.Tags[I];
    const FS08BoardFighter* F = (bTagsActive && I < Alive.Num()) ? Alive[I] : nullptr;
    if (!F) {
      T.FighterId.Reset();
      T.Planned = FS08ScreenRect();
      continue;
    }
    const AS08FighterActor* Actor = BoardActor->FindFighterActor(F->Id);
    // D-1 mode rule: the plate owner is hidden (the plate shows the same); -ArtPreviewTagNames=all -> full; K2 ->
    // compact; hover / selection -> full; a grey blockout (no art sculpt) -> full; the art sculpt -> compact.
    // W5b-R r3 (t53 revision 1, tags.mode): the plate owner is hidden only while the plate reads as the owner's
    // (ChoosePlateRect bound); a plate pushed away by K-2 (Cobble: reachable cells all around Medusa, the plate
    // lands next to Merlin) keeps a compact tag at the figure, so the HP stays next to it on both clients.
    // W7: ChoosePlateRect's on-owner fallback now keeps that Cobble plate bound (over the owner's head); an unbound
    // plate is left only when no forbidden-free bound place exists at all.
    ES08TagMode Mode = ES08TagMode::Compact;
    if (ArtHud.bPlateVisible && F->Id == ArtHud.PlateFighterId) {
      Mode = ArtHud.PlateResult.bBound ? ES08TagMode::Hidden : ES08TagMode::Compact;
    } else if (ArtHud.bTagNamesAll) {
      Mode = ES08TagMode::Full;
    } else if (bK2) {
      Mode = ES08TagMode::Compact;
    } else if (F->Id == ArtHud.HoveredFighterId || F->Id == SelectedId) {
      Mode = ES08TagMode::Full;
    } else if (!Actor || !Actor->HasArtSculpt()) {
      Mode = ES08TagMode::Full;
    }
    const ES08TeamSlot Team = BoardActor->TeamOfFighter(*F);
    const ES08TeamSlot Look =
        S08TeamLook(Team, F->OwnerId == ViewerId, static_cast<ES08TeamColorMode>(ArtHud.TeamColorMode));
    const FString Key = FString::Printf(TEXT("%s|%s|%d|%d|%d|%d"), *F->Id, *F->Label, F->Health, F->MaxHealth,
                                        static_cast<int32>(Mode), static_cast<int32>(Look));
    if (Key != T.ContentKey && T.Widget) {
      FS08TagTexts Texts;
      Texts.Name = FText::FromString(F->Label);  // fighter label: server data
      Texts.Hp = S08ArtHudText::HpLabel(F->Health, F->MaxHealth);
      Texts.HpFraction = F->MaxHealth > 0 ? static_cast<float>(F->Health) / F->MaxHealth : 0.0f;
      Texts.TeamSlot = Look == ES08TeamSlot::P1 ? 0 : 1;
      Texts.Mode = Mode;
      T.Widget->ApplyModel(Texts);
      T.ContentKey = Key;
    }
    if (T.Widget) T.Widget->SetBoardPlate(bBoardPlates);  // no-op while unchanged (grids: always off)
    T.FighterId = F->Id;
    T.Mode = static_cast<uint8>(Mode);
    T.TeamSlot = Look == ES08TeamSlot::P1 ? 0 : 1;
    T.Figure = Figures[F->Id];
    Signature += Key + S08ArtHud::FormatRect(T.Figure);
  }
  // ---- the live damage number (the latest seq)
  FString DamageId;
  int32 DamageSeq = -1, DamageAmount = 0;
  if (bTagsActive && ArtHud.DamageWidget) {
    for (const FString& Id : BoardActor->GetActiveDamageNumberIds()) {
      const int32 Seq = BoardActor->GetDamageNumberSeq(Id);
      if (Seq > DamageSeq) {
        DamageSeq = Seq;
        DamageId = Id;
        DamageAmount = BoardActor->GetDamageNumberAmount(Id);
      }
    }
  }
  Signature += FString::Printf(TEXT("|dmg=%s@%d|plate=%s|"), *DamageId, DamageSeq,
                               ArtHud.bPlateVisible ? *S08ArtHud::FormatRect(ArtHud.PlatePlanned) : TEXT("-"));
  for (const FS08ScreenRect& P : Panels) Signature += S08ArtHud::FormatRect(P);
  if (!IconTarget.IsEmpty() && Figures.Contains(IconTarget)) Signature += S08ArtHud::FormatRect(Figures[IconTarget]);

  const bool bRelayout = Signature != ArtHud.LabelSignature;
  if (!bRelayout) {
    if (ArtHud.bDamageVisible) ++ArtHud.DamageStableFrames;
    return;
  }
  ArtHud.LabelSignature = Signature;

  // ---- deterministic layout: plate (placed) -> priority tags -> icon -> damage number -> other tags (far first)
  TArray<FS08ScreenRect> Hard = Panels;
  if (ArtHud.bPlateVisible) Hard.Add(ArtHud.PlatePlanned);
  auto OthersOf = [&Figures](const FString& Id) {
    TArray<FS08ScreenRect> Out;
    for (const TPair<FString, FS08ScreenRect>& Pair : Figures) {
      if (Pair.Key != Id) Out.Add(Pair.Value);
    }
    return Out;
  };
  int32 Order = 0;
  auto PlaceTag = [&](FS08ArtHudRuntime::FTagSlot& T) {
    const FVector2D Desired = T.Widget ? S08ArtHudPrepassSize(*T.Widget) : FVector2D::ZeroVector;
    // W5b-R r3 (t53 revision 1, tags.binding): bound to the owner's figure, inset fallback, first two rings
    const S08ArtHud::FLabelPlacementInput In = S08ArtHud::MakeTagPlacementInput(
        ViewportPx, FVector2D(FMath::CeilToFloat(Desired.X * Ppu), FMath::CeilToFloat(Desired.Y * Ppu)), T.Figure,
        OthersOf(T.FighterId), Hard, TagHardPadPx);
    const S08ArtHud::FLabelPlacementResult R = S08ArtHud::ChooseLabelRect(In);
    T.Planned = R.Rect;
    T.Candidate = R.Candidate;
    T.Ring = R.Ring;
    T.SoftArea = R.SoftArea;
    T.HardArea = R.HardArea;
    T.bBound = R.bBound;
    T.Order = Order++;
    if (!R.Rect.IsEmpty()) Hard.Add(R.Rect);
  };
  TSet<int32> Placed;
  auto SlotOf = [this](const FString& Id) -> int32 {
    for (int32 I = 0; I < ArtHud.Tags.Num(); ++I) {
      if (!Id.IsEmpty() && ArtHud.Tags[I].FighterId == Id &&
          static_cast<ES08TagMode>(ArtHud.Tags[I].Mode) != ES08TagMode::Hidden) {
        return I;
      }
    }
    return INDEX_NONE;
  };
  for (const FString& Priority : {IconTarget, DamageId}) {
    const int32 I = SlotOf(Priority);
    if (I != INDEX_NONE && !Placed.Contains(I)) {
      PlaceTag(ArtHud.Tags[I]);
      Placed.Add(I);
    }
  }
  // D-5 icon anchors: right / left / below / above, avoiding other figures (with rings), placed tags, plate, panels.
  FS08ScreenRect IconRect;
  if (bActive && !IconTarget.IsEmpty() && ArtHud.bIconTextureReady && Figures.Contains(IconTarget)) {
    S08ArtHud::FIconAnchorInput In;
    In.Viewport = ViewportPx;
    In.Size = static_cast<float>(ArtHud.IconSize);
    In.Target = Figures[IconTarget];
    In.Figures = OthersOf(IconTarget);
    In.Hard = Hard;
    const S08ArtHud::FIconAnchorResult R = S08ArtHud::ChooseIconAnchor(In);
    IconRect = R.Rect;
    ArtHud.IconAnchor = R.Anchor;
    ArtHud.bIconFallback = R.bFallback;
    ArtHud.IconOverlap = R.OverlapArea;
    if (!IconRect.IsEmpty()) Hard.Add(IconRect);
  }
  // D-1 damage number: right of the target's tag, above it, left; never over a tag, the icon, the plate or the
  // target's figure; priority over the tags of uninvolved fighters (placed below). W5b-R: bound to the target
  // (centre nearer the target's figure than any other figure; T5.2 r1 rehearsal: above Arthur's left tag it sat
  // nearer a harpy).
  FS08ScreenRect DamageRect;
  FString DamageCandidate = TEXT("none");
  if (!DamageId.IsEmpty() && ArtHud.DamageWidget) {
    ArtHud.DamageWidget->ApplyAmount(S08ArtHudText::DamageNumber(DamageAmount));
    const FVector2D Desired = S08ArtHudPrepassSize(*ArtHud.DamageWidget);
    const int32 TagIndex = SlotOf(DamageId);
    FS08ScreenRect Anchor = TagIndex != INDEX_NONE ? ArtHud.Tags[TagIndex].Planned : FS08ScreenRect();
    FS08ScreenRect TargetFigure;
    if (const FS08ScreenRect* Fig = Figures.Find(DamageId)) {
      TargetFigure = *Fig;
    } else if (const FS08BoardFighter* Dead = FindFighter(DamageId)) {
      // a fighter the damage defeated: its cell (a figure-sized box at the cell) is the anchor
      FVector2D C;
      if (Dead->X >= 0 && ProjectToViewport(BoardModel.CellToWorld(Dead->X, Dead->Y), C)) {
        TargetFigure = FS08ScreenRect(C.X - 30.0f, C.Y - 60.0f, C.X + 30.0f, C.Y + 10.0f);
      }
    }
    if (Anchor.IsEmpty()) Anchor = TargetFigure;
    if (!Anchor.IsEmpty()) {
      S08ArtHud::FLabelPlacementInput In;
      In.Viewport = ViewportPx;
      In.Size = FVector2D(FMath::CeilToFloat(Desired.X * Ppu), FMath::CeilToFloat(Desired.Y * Ppu));
      In.Anchor = Anchor;
      In.Hard = Hard;
      if (!TargetFigure.IsEmpty()) In.Hard.Add(TargetFigure);
      In.Soft = OthersOf(DamageId);
      In.bRightFirst = true;
      // t53 damage.binding: the number reads as the target's - its centre nearer the target figure than any other
      In.BindTarget = TargetFigure;
      In.BindOthers = OthersOf(DamageId);
      const S08ArtHud::FLabelPlacementResult R = S08ArtHud::ChooseLabelRect(In);
      DamageRect = R.Rect;
      DamageCandidate = R.Candidate + FString::Printf(TEXT(" ring=%d hardPx2=%.0f softPx2=%.0f"), R.Ring, R.HardArea,
                                                      R.SoftArea);
      if (!DamageRect.IsEmpty()) Hard.Add(DamageRect);
    }
  }
  // the other tags, far (small screen Y) to near
  TArray<int32> Rest;
  for (int32 I = 0; I < ArtHud.Tags.Num(); ++I) {
    const FS08ArtHudRuntime::FTagSlot& T = ArtHud.Tags[I];
    if (!Placed.Contains(I) && !T.FighterId.IsEmpty() && static_cast<ES08TagMode>(T.Mode) != ES08TagMode::Hidden) {
      Rest.Add(I);
    }
  }
  Rest.Sort([this](int32 A, int32 B) {
    const FS08ArtHudRuntime::FTagSlot& TA = ArtHud.Tags[A];
    const FS08ArtHudRuntime::FTagSlot& TB = ArtHud.Tags[B];
    return TA.Figure.Y0 != TB.Figure.Y0 ? TA.Figure.Y0 < TB.Figure.Y0 : TA.FighterId < TB.FighterId;
  });
  for (const int32 I : Rest) PlaceTag(ArtHud.Tags[I]);

  // ---- apply: tags
  const bool bSettled = CameraZoom.IsSettled();
  for (FS08ArtHudRuntime::FTagSlot& T : ArtHud.Tags) {
    const bool bShow = !T.FighterId.IsEmpty() && static_cast<ES08TagMode>(T.Mode) != ES08TagMode::Hidden &&
                       !T.Planned.IsEmpty();
    if (T.Slot && bShow) T.Slot->SetOffset(FMargin(T.Planned.X0 / Ppu, T.Planned.Y0 / Ppu, 0.0f, 0.0f));
    if (T.Widget && bShow != T.bShown) {
      T.Widget->SetVisibility(bShow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    }
    T.bShown = bShow;
    if (bShow && bSettled) {
      FS08Trace::Write(FString::Printf(
          TEXT("TAG fighter=%s bbox=%s mode=%s look=%s placement=%s ring=%d hardPx2=%.0f softPx2=%.0f order=%d bound=%d"),
          *T.FighterId, *S08ArtHud::FormatRect(T.Planned), S08TagModeName(static_cast<ES08TagMode>(T.Mode)),
          T.TeamSlot ? TEXT("P2") : TEXT("P1"), *T.Candidate, T.Ring, T.HardArea, T.SoftArea, T.Order,
          T.bBound ? 1 : 0));
    }
  }
  // ---- apply: icon (views keep the exact-size brush)
  if (IconRect.IsEmpty()) {
    if (ArtHud.bIconVisible) {
      for (const TSharedPtr<IS08ArtIconView>& View : ArtHud.IconViews) View->SetShown(false);
      ArtHud.bIconVisible = false;
      FS08Trace::Write(FString::Printf(TEXT("HUD icon hidden fighter=%s"), *ArtHud.IconFighterId));
      ArtHud.IconFighterId.Reset();
    }
  } else {
    const float N = static_cast<float>(ArtHud.IconSize);
    const FVector2D ImageSize(N / Ppu, N / Ppu);
    const bool bBrushChanged = !FMath::IsNearlyEqual(static_cast<double>(ArtHud.IconBrush.ImageSize.X), ImageSize.X, 1e-4) ||
                               !FMath::IsNearlyEqual(static_cast<double>(ArtHud.IconBrush.ImageSize.Y), ImageSize.Y, 1e-4);
    ArtHud.IconBrush.ImageSize = ImageSize;
    const bool bAlternate = static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate;
    for (int32 Index = 0; Index < ArtHud.IconViews.Num(); ++Index) {
      const TSharedPtr<IS08ArtIconView>& View = ArtHud.IconViews[Index];
      View->Slot->SetOffset(FMargin(IconRect.X0 / Ppu, IconRect.Y0 / Ppu, N / Ppu, N / Ppu));
      if (bBrushChanged) View->SetIconBrush(ArtHud.IconBrush);
      if (!ArtHud.bIconVisible) View->SetShown(ArtHud.IsViewShown(Index, bAlternate));
    }
    ArtHud.bIconVisible = true;
    ArtHud.IconFighterId = IconTarget;
    ArtHud.IconSource = IconSource;
    ArtHud.IconPlanned = IconRect;
    if (bSettled) {
      FS08Trace::Write(FString::Printf(
          TEXT("ICON fighter=%s bbox=%s size=%d src=%s anchor=%s fallback=%d overlapPx2=%.0f texture=%s"), *IconTarget,
          *S08ArtHud::FormatRect(IconRect), ArtHud.IconSize, *IconSource, *ArtHud.IconAnchor,
          ArtHud.bIconFallback ? 1 : 0, ArtHud.IconOverlap, *ArtHud.IconTexturePath));
    }
  }
  // ---- apply: damage number
  const bool bShowDamage = !DamageRect.IsEmpty();
  if (ArtHud.DamageWidget) {
    if (bShowDamage && ArtHud.DamageSlot) {
      ArtHud.DamageSlot->SetOffset(FMargin(DamageRect.X0 / Ppu, DamageRect.Y0 / Ppu, 0.0f, 0.0f));
    }
    if (bShowDamage != ArtHud.bDamageVisible) {
      ArtHud.DamageWidget->SetVisibility(bShowDamage ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    }
  }
  const bool bDamageMoved = bShowDamage != ArtHud.bDamageVisible || ArtHud.DamageFighterId != DamageId ||
                            ArtHud.DamageSeq != DamageSeq ||
                            !FMath::IsNearlyEqual(ArtHud.DamagePlanned.X0, DamageRect.X0, 0.5f) ||
                            !FMath::IsNearlyEqual(ArtHud.DamagePlanned.Y0, DamageRect.Y0, 0.5f);
  ArtHud.DamageStableFrames = bShowDamage ? (bDamageMoved ? 0 : ArtHud.DamageStableFrames + 1) : 0;
  if (bShowDamage && bDamageMoved) {
    FS08Trace::Write(FString::Printf(TEXT("DAMAGE fighter=%s bbox=%s amount=%d seq=%d placement=%s"), *DamageId,
                                     *S08ArtHud::FormatRect(DamageRect), DamageAmount, DamageSeq, *DamageCandidate));
  }
  ArtHud.bDamageVisible = bShowDamage;
  ArtHud.DamageFighterId = DamageId;
  ArtHud.DamageSeq = DamageSeq;
  ArtHud.DamageAmount = DamageAmount;
  ArtHud.DamagePlanned = DamageRect;
  ArtHud.DamageCandidate = DamageCandidate;
}

void AS08FlowGameMode::HandleEndFrame() {
  if (ArtHud.LateShots.Num() == 0) return;
  const TArray<FS08ArtHudRuntime::FLateShot> Shots = MoveTemp(ArtHud.LateShots);
  ArtHud.LateShots.Reset();
  for (const FS08ArtHudRuntime::FLateShot& Shot : Shots) WriteArtHudLateLines(Shot.File, Shot.RequestFrame);
}

void AS08FlowGameMode::WriteArtHudLateLines(const FString& File, uint64 RequestFrame) {
  const unsigned long long Frame = static_cast<unsigned long long>(GFrameCounter);
  const FString FrameField = FString::Printf(TEXT("frame=%llu"), Frame);
  FS08Trace::Write(FString::Printf(TEXT("SHOT late begin file=%s frame=%llu requestFrame=%llu"), *File, Frame,
                                   static_cast<unsigned long long>(RequestFrame)));
  if (BoardActor && BoardActor->IsArtActive()) {
    auto Painted = [this](const TSharedPtr<SWidget>& Widget, const FS08ScreenRect& Planned, FS08ScreenRect& Out) {
      return Widget.IsValid() && Widget->GetVisibility().IsVisible() && WidgetViewportRect(Widget, Out) &&
             !Out.IsEmpty() && (Planned.IsEmpty() || (FMath::Abs(Out.X0 - Planned.X0) <= 1.5f &&
                                                      FMath::Abs(Out.Y0 - Planned.Y0) <= 1.5f));
    };
    // combat icon: a line only when the icon is REALLY on screen at the end of this frame
    if (ArtHud.IconViews.Num() > 0) {
      const TSharedPtr<SWidget> Root = ArtHud.IconViews[S08ShownViewIndex(ArtHud, ArtHud.IconViews.Num())]->GetRoot();
      FS08ScreenRect Rect;
      const bool bVisible = ArtHud.bIconVisible && Root->GetVisibility().IsVisible();
      if (bVisible) {
        const bool bPainted = Painted(Root, ArtHud.IconPlanned, Rect);
        FS08Trace::Write(FString::Printf(
            TEXT("SHOT icon fighter=%s bbox=%s size=%d src=%s planned=%s geom=%s visible=1 anchor=%s fallback=%d overlapPx2=%.0f texture=%s %s"),
            *ArtHud.IconFighterId, *S08ArtHud::FormatRect(bPainted ? Rect : ArtHud.IconPlanned), ArtHud.IconSize,
            *ArtHud.IconSource, *S08ArtHud::FormatRect(ArtHud.IconPlanned), bPainted ? TEXT("painted") : TEXT("planned"),
            *ArtHud.IconAnchor, ArtHud.bIconFallback ? 1 : 0, ArtHud.IconOverlap, *ArtHud.IconTexturePath, *FrameField));
      } else {
        FS08Trace::Write(FString::Printf(TEXT("SHOT iconstate visible=0 lastFighter=%s %s"),
                                         ArtHud.IconFighterId.IsEmpty() ? TEXT("none") : *ArtHud.IconFighterId,
                                         *FrameField));
      }
    }
    WriteArtHudWidgetLines(FString(), /*bLate=*/true);
    // screen tags
    for (const FS08ArtHudRuntime::FTagSlot& T : ArtHud.Tags) {
      if (!T.Widget || T.FighterId.IsEmpty()) continue;
      TArray<FS08WidgetPart> Parts;
      T.Widget->CollectParts(Parts);
      const TSharedPtr<SWidget> Root = T.Widget->GetCachedWidget();
      FS08ScreenRect RootRect;
      const bool bRootPainted = T.bShown && Painted(Root, T.Planned, RootRect);
      const ES08TagMode Mode = static_cast<ES08TagMode>(T.Mode);
      for (const FS08WidgetPart& Part : Parts) {
        FS08ScreenRect Rect;
        const bool bVisible = T.bShown && Part.Widget.IsValid() && Part.Widget->GetVisibility().IsVisible() &&
                              Root.IsValid() && Root->GetVisibility().IsVisible();
        const bool bPainted = bVisible && bRootPainted && WidgetViewportRect(Part.Widget, Rect) && !Rect.IsEmpty();
        FString Extra = FString::Printf(
            TEXT("mode=%s look=%s shape=%s placement=%s ring=%d order=%d bound=%d softPx2=%.0f planned=%s %s"),
            S08TagModeName(Mode), T.TeamSlot ? TEXT("P2") : TEXT("P1"), T.TeamSlot ? TEXT("hex") : TEXT("circle"),
            *T.Candidate, T.Ring, T.Order, T.bBound ? 1 : 0, T.SoftArea, *S08ArtHud::FormatRect(T.Planned),
            *FrameField);
        if (Part.Id == S08ArtHudIds::TagName) Extra += FString::Printf(TEXT(" font=%d"), T.Widget->NameFontSize());
        if (Part.Id == S08ArtHudIds::TagHp) Extra += FString::Printf(TEXT(" font=%d"), T.Widget->HpFontSize());
        FS08Trace::Write(S08ArtHud::FormatWidgetLineEx(Part.Id, TEXT("umg"), S08TagModeName(Mode), T.FighterId, Rect,
                                                       bPainted, bVisible, US08ArtTagWidget::WidgetBlueprintPath, Extra));
      }
    }
    // damage number
    if (ArtHud.DamageWidget && ArtHud.bDamageVisible) {
      TArray<FS08WidgetPart> Parts;
      ArtHud.DamageWidget->CollectParts(Parts);
      const TSharedPtr<SWidget> Root = ArtHud.DamageWidget->GetCachedWidget();
      FS08ScreenRect RootRect;
      const bool bRootPainted = Painted(Root, ArtHud.DamagePlanned, RootRect);
      for (const FS08WidgetPart& Part : Parts) {
        FS08ScreenRect Rect;
        const bool bVisible = Part.Widget.IsValid() && Part.Widget->GetVisibility().IsVisible() && Root.IsValid() &&
                              Root->GetVisibility().IsVisible();
        const bool bPainted = bVisible && bRootPainted && WidgetViewportRect(Part.Widget, Rect) && !Rect.IsEmpty();
        FString Extra = FString::Printf(TEXT("amount=%d seq=%d placement=%s stableFrames=%d planned=%s %s"),
                                        ArtHud.DamageAmount, ArtHud.DamageSeq, *ArtHud.DamageCandidate.Replace(TEXT(" "), TEXT("_")),
                                        ArtHud.DamageStableFrames, *S08ArtHud::FormatRect(ArtHud.DamagePlanned),
                                        *FrameField);
        if (Part.Id == S08ArtHudIds::DamageText) Extra += FString::Printf(TEXT(" font=%d"), ArtHud.DamageWidget->FontSize());
        FS08Trace::Write(S08ArtHud::FormatWidgetLineEx(Part.Id, TEXT("umg"), TEXT("damage"), ArtHud.DamageFighterId, Rect,
                                                       bPainted, bVisible, US08ArtDamageWidget::WidgetBlueprintPath, Extra));
      }
      if (bRootPainted) {
        // qa010 / t52 vocabulary: the painted box of the number
        FS08Trace::Write(FString::Printf(TEXT("SHOT damage fighter=%s bbox=%s %s"), *ArtHud.DamageFighterId,
                                         *S08ArtHud::FormatRect(RootRect), *FrameField));
      }
    }
    // HUD panels (K3 rule D-10)
    const TCHAR* PanelIds[] = {TEXT("hud.command"), TEXT("hud.side"), TEXT("hud.hand")};
    const TWeakPtr<SWidget> PanelWidgets[] = {ArtHud.CommandPanel, ArtHud.SidePanel, ArtHud.HandPanel};
    for (int32 I = 0; I < 3; ++I) {
      const TSharedPtr<SWidget> Panel = PanelWidgets[I].Pin();
      FS08ScreenRect Rect;
      const bool bVisible = Panel.IsValid() && Panel->GetVisibility().IsVisible();
      const bool bPainted = bVisible && WidgetViewportRect(Panel, Rect) && !Rect.IsEmpty();
      FS08Trace::Write(FString::Printf(TEXT("SHOT panel id=%s bbox=%s geom=%s visible=%d %s"), PanelIds[I],
                                       *S08ArtHud::FormatRect(bPainted ? Rect : FS08ScreenRect()),
                                       bPainted ? TEXT("painted") : TEXT("unpainted"), bVisible ? 1 : 0, *FrameField));
    }
    // world labels (grey path / -S08LegacyRender): what is really visible now
    for (const FS08BoardFighter& F : Fighters) {
      const AS08FighterActor* Actor = BoardActor->FindFighterActor(F.Id);
      FBox Box;
      if (!Actor || !F.IsAlive() || !Actor->GetVisibleLabelBox(Box)) continue;
      TArray<FVector2D> Corners;
      for (int32 C = 0; C < 8; ++C) {
        FVector2D S;
        const FVector P((C & 1) ? Box.Max.X : Box.Min.X, (C & 2) ? Box.Max.Y : Box.Min.Y,
                        (C & 4) ? Box.Max.Z : Box.Min.Z);
        if (ProjectToViewport(P, S)) Corners.Add(S);
      }
      if (Corners.Num() != 8) continue;
      const ES08FighterLabelMode Mode = Actor->GetLabelMode();
      FS08Trace::Write(FString::Printf(TEXT("SHOT label fighter=%s mode=%s bbox=%s %s"), *F.Id,
                                       Mode == ES08FighterLabelMode::Compact ? TEXT("compact")
                                       : Mode == ES08FighterLabelMode::Hidden ? TEXT("hidden") : TEXT("full"),
                                       *S08ArtHud::FormatRect(FS08ScreenRect::FromPoints(Corners)), *FrameField));
    }
  }
  FS08Trace::Write(FString::Printf(TEXT("SHOT late end file=%s frame=%llu"), *File, Frame));
}

void AS08FlowGameMode::HandleScreenshotCaptured(int32 Width, int32 Height, const TArray<FColor>& Colors) {
  // The engine calls this INSTEAD of writing the PNG (GameViewportClient.cpp ProcessScreenShots: a bound delegate
  // receives the pixels, alpha forced to 255). Save them to the requested path and write the provenance line:
  // sha256 over the raw pixel bytes in memory order B,G,R,A (FColor on little-endian Windows).
  const FString Path = ArtHud.PendingCapturePath;
  const uint64 RequestFrame = ArtHud.PendingCaptureRequestFrame;
  ArtHud.PendingCapturePath.Reset();
  const FString Sha = S08Sha256Hex(reinterpret_cast<const uint8*>(Colors.GetData()),
                                   static_cast<int64>(Colors.Num()) * static_cast<int64>(sizeof(FColor)));
  bool bSaved = false;
  if (!Path.IsEmpty() && Colors.Num() == Width * Height) {
    TArray64<uint8> Png;
    FImageUtils::PNGCompressImageArray(Width, Height, Colors, Png);
    bSaved = Png.Num() > 0 && FFileHelper::SaveArrayToFile(Png, *Path);
  }
  const FString Line = FString::Printf(TEXT("SHOT captured file=%s frame=%llu px=%dx%d sha256=%s order=BGRA saved=%d"),
                                       Path.IsEmpty() ? TEXT("-") : *FPaths::GetCleanFilename(Path),
                                       static_cast<unsigned long long>(GFrameCounter), Width, Height, *Sha,
                                       bSaved ? 1 : 0);
  TraceLines.Add(Line);
  FS08Trace::Write(Line);
  // W5b-R: the late SHOT section of THIS capture. FSlateApplication::TakeScreenshot has just painted the window for
  // these pixels, so the cached widget geometry and the icon / tag / damage state are exactly what the PNG shows.
  // A request whose capture slips to the next frame (T5.2 combat-result: the icon was hidden in between) got an
  // end-of-frame section for the request frame already; this second section supersedes it (parsers take the last).
  if (!Path.IsEmpty()) {
    const FString File = FPaths::GetCleanFilename(Path);
    ArtHud.LateShots.RemoveAll([&File](const FS08ArtHudRuntime::FLateShot& S) { return S.File == File; });
    WriteArtHudLateLines(File, RequestFrame);
  }
}

void AS08FlowGameMode::RunArtPreviewInputPlan() {
  if (ArtHud.Plan.Num() == 0 || ArtHud.bPlanDone || ArtHud.PlanStartAt < 0.0f) return;
  if (!CameraZoom.IsReady() || Elapsed < ArtHud.PlanStartAt || Elapsed < ArtHud.PlanNextAt) return;
  // Never before this client's evidence shot: the K2 frame stays the flag
  // selection + focus zoom frame of T1.1.
  if (ArtPreviewShotAfter >= 0.0f && !AutoShotPath.IsEmpty() && !bShotTaken) return;
  const ES08InputStep Step = ArtHud.Plan[ArtHud.PlanIndex++];
  FS08Trace::Write(FString::Printf(TEXT("INPUT step src=flag index=%d/%d step=%s"), ArtHud.PlanIndex,
                                   ArtHud.Plan.Num(), S08InputStepName(Step)));
  EmulateInputStep(Step);
  ArtHud.PlanNextAt = Elapsed + ArtHud.PlanStepSeconds;
  if (ArtHud.PlanIndex >= ArtHud.Plan.Num()) {
    ArtHud.bPlanDone = true;
    FS08Trace::Write(FString::Printf(TEXT("INPUT plan done src=flag steps=%d zoom=%.2f dist=%.1f"),
                                     ArtHud.Plan.Num(), CameraZoom.ZoomOf(CameraZoom.Target), CameraZoom.Target));
  }
}

void AS08FlowGameMode::EmulateInputStep(ES08InputStep Step) {
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor || !Flow.IsValid()) return;
  switch (Step) {
    case ES08InputStep::WheelIn: ApplyWheel(+1, ES08InputSource::Flag); return;
    case ES08InputStep::WheelOut: ApplyWheel(-1, ES08InputSource::Flag); return;
    case ES08InputStep::Space: ApplySpace(ES08InputSource::Flag); return;
    default: break;
  }
  // Clicks: a screen point from the same projection the SHOT lines use, then
  // the visibility hit test GetHitResultUnderCursor performs for a real
  // click. Local effects only (own-fighter selection); cells are dry-run.
  const FS08BoardFighter* Hero = nullptr;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.OwnerId == Flow->GetUserId() && F.bIsHero && F.IsAlive()) Hero = &F;
  }
  FVector World = FVector::ZeroVector;
  FString Expect = TEXT("none");
  if (Step == ES08InputStep::ClickCell) {
    FString SelectedId;
    TSet<uint64> Legal;
    CurrentSelection(SelectedId, Legal);
    FIntPoint Own(-1, -1);
    if (const FS08BoardFighter* Selected = FindFighter(SelectedId)) Own = FIntPoint(Selected->X, Selected->Y);
    const TArray<FIntPoint> Destinations = S08ArtHud::DestinationCells(Legal, Own);
    if (Destinations.Num() == 0) {
      FS08Trace::Write(TEXT("INPUT click button=left src=flag step=clickcell skipped=no-destination"));
      return;
    }
    // The destination nearest to the screen centre (it is on screen at K2).
    FVector2D Best(0, 0);
    float BestD = MAX_flt;
    FVector2D ViewportPx(0.0, 0.0);
    GEngine->GameViewport->GetViewportSize(ViewportPx);
    for (const FIntPoint& Cell : Destinations) {
      FVector2D S;
      const FVector W = BoardModel.CellToWorld(Cell.X, Cell.Y);
      if (!ProjectToViewport(W, S)) continue;
      const float D = static_cast<float>(FVector2D::Distance(S, ViewportPx * 0.5));
      if (D < BestD) {
        BestD = D;
        World = W;
        Expect = FString::Printf(TEXT("cell(%d,%d)"), Cell.X, Cell.Y);
      }
    }
  } else if (Hero) {
    const AS08FighterActor* Actor = BoardActor->FindFighterActor(Hero->Id);
    const float Height = Actor ? Actor->GetFigureHeightUU() : 60.0f;
    World = BoardModel.CellToWorld(Hero->X, Hero->Y) +
            FVector(0.0f, 0.0f, Step == ES08InputStep::ClickHero ? Height * 0.5f : Height + 35.0f);
    Expect = Step == ES08InputStep::ClickHero ? Hero->Id : FString::Printf(TEXT("not:%s"), *Hero->Id);
  } else {
    FS08Trace::Write(FString::Printf(TEXT("INPUT click button=left src=flag step=%s skipped=no-own-hero"),
                                     S08InputStepName(Step)));
    return;
  }
  FVector2D Screen;
  if (!ProjectToViewport(World, Screen)) {
    FS08Trace::Write(FString::Printf(TEXT("INPUT click button=left src=flag step=%s skipped=not-projected"),
                                     S08InputStepName(Step)));
    return;
  }
  FHitResult Hit;
  const bool bHit = PC->GetHitResultAtScreenPosition(Screen, ECC_Visibility, false, Hit);
  const AS08FighterActor* FighterActor = bHit ? Cast<AS08FighterActor>(Hit.GetActor()) : nullptr;
  int32 CellX = -1, CellY = -1;
  const bool bCell = bHit && !FighterActor && BoardActor->WorldToCell(Hit.ImpactPoint, CellX, CellY);
  FString SelectedId;
  TSet<uint64> Legal;
  CurrentSelection(SelectedId, Legal);
  const bool bReachable = bCell && Legal.Contains(FS08BoardModel::CellKey(CellX, CellY));
  const FString HitFighter = FighterActor ? FighterActor->GetFighterId() : FString(TEXT("none"));
  bool bMatch = false;
  if (Step == ES08InputStep::ClickHero) bMatch = Hero && HitFighter == Hero->Id;
  else if (Step == ES08InputStep::ClickAbove) bMatch = Hero && HitFighter != Hero->Id;
  else bMatch = bCell && Expect == FString::Printf(TEXT("cell(%d,%d)"), CellX, CellY);
  bool bSelected = false;
  if (FighterActor && FighterActor->GetFighter().OwnerId == Flow->GetUserId() &&
      CommandUi.Mode == ES09CommandMode::None) {
    SelectFighter(FighterActor->GetFighterId());  // local selection, no server command
    bSelected = true;
  }
  FS08Trace::Write(FString::Printf(
      TEXT("INPUT click button=left src=flag step=%s screen=(%.0f,%.0f) hit=%d actor=%s comp=%s fighter=%s cell=(%d,%d) reachable=%d expect=%s match=%d dispatch=0 selected=%d"),
      S08InputStepName(Step), Screen.X, Screen.Y, bHit ? 1 : 0,
      Hit.GetActor() ? *Hit.GetActor()->GetName() : TEXT("none"),
      Hit.GetComponent() ? *Hit.GetComponent()->GetName() : TEXT("none"), *HitFighter,
      bCell ? CellX : -1, bCell ? CellY : -1, bReachable ? 1 : 0, *Expect, bMatch ? 1 : 0, bSelected ? 1 : 0));
}

void AS08FlowGameMode::WriteArtHudShotLines() {
  if (!BoardActor || !BoardActor->IsArtActive()) return;
  FString SelectedId;
  TSet<uint64> Legal;
  CurrentSelection(SelectedId, Legal);
  FIntPoint OwnCell(-1, -1);
  if (const FS08BoardFighter* Selected = FindFighter(SelectedId)) OwnCell = FIntPoint(Selected->X, Selected->Y);
  const TArray<FIntPoint> Destinations = S08ArtHud::DestinationCells(Legal, OwnCell);
  if (!SelectedId.IsEmpty() || ArtHud.bPlateVisible) {
    FS08Trace::Write(FString::Printf(
        TEXT("SHOT selection fighter=%s ownCell=(%d,%d) legal=%d destinations=%d ownCellExcluded=%d plateFighter=%s"),
        SelectedId.IsEmpty() ? TEXT("none") : *SelectedId, OwnCell.X, OwnCell.Y, Legal.Num(), Destinations.Num(),
        Legal.Contains(FS08BoardModel::CellKey(OwnCell.X, OwnCell.Y)) ? 1 : 0,
        ArtHud.bPlateVisible ? *ArtHud.PlateFighterId : TEXT("none")));
    FS08Trace::Write(FString::Printf(TEXT("SHOT reachable fighter=%s n=%d cells=%s"),
                                     SelectedId.IsEmpty() ? TEXT("none") : *SelectedId, Destinations.Num(),
                                     *S08ArtHud::FormatCells(Destinations)));
  }
  if (ArtHud.bPlateVisible) {
    // Painted geometry of the last frame; a plate that has not been painted
    // at its current place yet is written as a zero box (qa010: trace error,
    // never a pass).
    FS08ScreenRect Painted;
    const bool bPainted = ArtHud.PlateStableFrames >= 2 &&
                          WidgetViewportRect(TSharedPtr<SWidget>(ArtHud.PlateViews[S08ShownViewIndex(ArtHud, ArtHud.PlateViews.Num())]->GetRoot()), Painted) &&
                          !Painted.IsEmpty();
    const FS08ScreenRect Used = bPainted ? Painted : FS08ScreenRect();
    const int32 Overlap = S08ArtHud::CountOverlaps(Used, ProjectCells(Destinations), S08ArtHud::OverlapEpsilonPx2);
    FS08Trace::Write(FString::Printf(
        TEXT("SHOT plate fighter=%s bbox=%s overlapReachable=%d placement=%s gap=%.0f anchor=%s planned=%s geom=%s stableFrames=%d"),
        *ArtHud.PlateFighterId, *S08ArtHud::FormatRect(Used), Overlap, *ArtHud.PlateCandidate,
        S08RectGap(ArtHud.PlatePlanned, ArtHud.PlateAnchor), *S08ArtHud::FormatRect(ArtHud.PlateAnchor),
        *S08ArtHud::FormatRect(ArtHud.PlatePlanned), bPainted ? TEXT("painted") : TEXT("unpainted"),
        ArtHud.PlateStableFrames));
  }
  // W5b-R: each fighter's on-screen box (FigureScreenRect: base to figure top, with the team ring) - the "figure"
  // obstacle of the plate / icon / tag / damage rules and of the qa010 checks.
  for (const FS08BoardFighter& F : Fighters) {
    FS08ScreenRect R;
    if (!F.IsAlive() || !FigureScreenRect(F.Id, R)) continue;
    const AS08FighterActor* Actor = BoardActor->FindFighterActor(F.Id);
    const ES08TeamSlot Team = BoardActor->TeamOfFighter(F);
    FS08Trace::Write(FString::Printf(
        TEXT("SHOT figure fighter=%s bbox=%s ringR=%.2f art=%d blockout=%d team=%s look=%s ring=%d"), *F.Id,
        *S08ArtHud::FormatRect(R),
        (Actor && Actor->HasArtFigure()) ? (F.bIsHero ? S08TeamRingSpec::HeroRectRadiusUU
                                                      : S08TeamRingSpec::SidekickRectRadiusUU) : 30.0f,
        Actor && Actor->HasArtFigure() ? 1 : 0, Actor && Actor->IsBlockout() ? 1 : 0, S08TeamSlotName(Team),
        Actor ? S08TeamSlotName(Actor->GetLook()) : TEXT("-"), Actor && Actor->HasTeamRing() ? 1 : 0));
  }
}

void AS08FlowGameMode::WriteArtHudWidgetLines(const FString& Prefix, bool bLate) {
  // W4-C trace gate (engine gate memo, HUD row "gates by SHOT widget traces"):
  // the painted viewport-pixel bbox of every part of every view, one line per
  // part. Format (docs/art-pipeline/qa010/README.md):
  //   SHOT widget id=<ui-id> impl=<umg|slate> state=<own|enemy|combat|flag>
  //     fighter=<id> bbox=(x0,y0,x1,y1) geom=<painted|unpainted> visible=0|1 twin=0|1 source=<...>
  // twin=1 is the compare-mode Slate twin (render opacity 0, same slot
  // geometry): "bbox UMG = Slate +-1 px" compares the two on the SAME frame.
  // A part is "painted" once its view has kept its place for 2 frames.
  auto Emit = [this, &Prefix, bLate](const FS08WidgetPart& Part, const TCHAR* Impl, const TCHAR* State,
                                     const FString& Fighter, bool bStable, bool bTwin, const FString& Source) {
    FS08ScreenRect Rect;
    if (!bLate) {
      const bool bPainted = bStable && WidgetViewportRect(Part.Widget, Rect) && !Rect.IsEmpty();
      FS08Trace::Write(Prefix + S08ArtHud::FormatWidgetLine(Part.Id, Impl, State, Fighter, Rect, bPainted, bTwin, Source));
      return;
    }
    // W5b-R end of the requesting frame: the widget's ACTUAL visibility and painted geometry.
    const bool bVisible = Part.Widget.IsValid() && Part.Widget->GetVisibility().IsVisible() && !bTwin;
    const bool bPainted = bVisible && bStable && WidgetViewportRect(Part.Widget, Rect) && !Rect.IsEmpty();
    FS08Trace::Write(Prefix + S08ArtHud::FormatWidgetLineEx(
        Part.Id, Impl, State, Fighter, Rect, bPainted, bVisible, Source,
        FString::Printf(TEXT("frame=%llu"), static_cast<unsigned long long>(GFrameCounter))));
  };
  const bool bAlternate = static_cast<ES08ArtHudImpl>(ArtHud.Impl) == ES08ArtHudImpl::Alternate;
  if (ArtHud.bPlateVisible) {
    const FS08BoardFighter* Fighter = FindFighter(ArtHud.PlateFighterId);
    const bool bOwn = Fighter && Flow.IsValid() && Fighter->OwnerId == Flow->GetUserId();
    for (int32 Index = 0; Index < ArtHud.PlateViews.Num(); ++Index) {
      const TSharedPtr<IS08ArtPlateView>& View = ArtHud.PlateViews[Index];
      if (!ArtHud.IsViewShown(Index, bAlternate)) continue;  // collapsed: no painted geometry
      TArray<FS08WidgetPart> Parts;
      View->CollectParts(Parts);
      for (const FS08WidgetPart& Part : Parts) {
        Emit(Part, View->ImplName(), bOwn ? TEXT("own") : TEXT("enemy"), ArtHud.PlateFighterId,
             ArtHud.PlateStableFrames >= 2, View->bTwin, View->Source());
      }
    }
  }
  if (ArtHud.bIconVisible) {
    for (int32 Index = 0; Index < ArtHud.IconViews.Num(); ++Index) {
      const TSharedPtr<IS08ArtIconView>& View = ArtHud.IconViews[Index];
      if (!ArtHud.IsViewShown(Index, bAlternate)) continue;
      TArray<FS08WidgetPart> Parts;
      View->CollectParts(Parts);
      for (const FS08WidgetPart& Part : Parts) {
        Emit(Part, View->ImplName(), ArtHud.IconSource.IsEmpty() ? TEXT("none") : *ArtHud.IconSource,
             ArtHud.IconFighterId, true, View->bTwin, View->Source());
      }
    }
  }
}

// ---- W4-A render bench (-Bench) -------------------------------------------
// Backend-less, deterministic scene: the captured Cobble 5x6 game state
// (Config/Bench/S08BenchCobble.json, staged as UFS) goes through the same
// SyncBoardFromApplied path as a live snapshot, so the board, the light
// profile, the fighters and the game layer are exactly the -ArtPreview ones.
// Per view (default K1 + K2 5x on the viewer's hero): warm-up (first view),
// settle, a measurement window (frame / GPU / game / render thread ms; GPU
// from RHIGetGPUFrameCycles, which excludes idle bubbles on D3D12), optional
// CsvProfile Start/Stop (per-pass GPU with -csvGpuStats), ProfileGPU, then one
// SHOT with the RENDER fingerprint. Frame rate is unlimited (t.MaxFPS 0,
// VSync 0) unless -BenchFps=N. Flags: -Bench -ArtPreview -BenchOut=<dir>
// [-BenchFixture=<json>] [-BenchViews=K1+K2x5] [-BenchWarmup=30]
// [-BenchSettle=8] [-BenchMeasure=20] [-BenchCsv] [-BenchNoProfileGPU].
namespace {
struct FS08BenchState {
  bool bInit = false;
  int32 Step = 0;
  float NextAt = 0.0f;
  float Warmup = 30.0f;
  float Settle = 8.0f;
  float Measure = 20.0f;
  TArray<FString> Views;
  int32 View = 0;
  FString OutDir;
  bool bProfileGpu = true;
  bool bCsv = false;
  FString HeroId;
  FString ShotPath;
  float StepStart = 0.0f;
  bool bSettleLogged = false;
  TArray<float> FrameMs, GpuMs, GameMs, RenderMs;
};
FS08BenchState GS08Bench;

void S08BenchSetCvar(const TCHAR* Name, const FString& Value) {
  if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name)) {
    V->Set(*Value, ECVF_SetByConsole);
  }
}

float S08BenchViewZoom(const FString& View) {
  // "K1" = overview, "K2x5" = zoom 5 on the hero, "K2x1.6" = 1.6,
  // "K1x0.65" = wheel zoom-out of the overview (ENV-MAPS first frames).
  // ENV-U9: every zoom is relative to the overview, which on the map-image
  // boards is the fit x 1.25 = 2340.2 uu ("K1"); "K2x1.6" = 1462.6 uu there
  // (the pre-ENV-U9 K2x1.6 framing, 1170.1 uu, is "K2x2"); "K1x0.65" stops
  // at the far limit fit / 0.65 = 2880.2 uu (zoom 0.81, the same frame as
  // the first frames' K1x0.65); "K1x1.25" = a centred zoom-in with nothing
  // selected = the fit, 1872.2 uu (the pre-ENV-U9 K1 framing).
  int32 X = INDEX_NONE;
  if (View.FindChar(TCHAR('x'), X)) return FCString::Atof(*View.Mid(X + 1));
  return 1.0f;
}
} // namespace

void AS08FlowGameMode::RunRenderBench() {
  FS08BenchState& B = GS08Bench;
  if (B.Step == 99) return;
  auto Finish = [&](const FString& Line) {
    FS08Trace::Write(Line);
    FS08Trace::Close();
    B.Step = 99;
    FGenericPlatformMisc::RequestExit(false);
  };
  const TCHAR* Cmd = FCommandLine::Get();
  if (!B.bInit) {
    B.bInit = true;
    FParse::Value(Cmd, TEXT("BenchWarmup="), B.Warmup);
    FParse::Value(Cmd, TEXT("BenchSettle="), B.Settle);
    FParse::Value(Cmd, TEXT("BenchMeasure="), B.Measure);
    FString Views = TEXT("K1+K2x5");
    FParse::Value(Cmd, TEXT("BenchViews="), Views);
    Views.ParseIntoArray(B.Views, TEXT("+"), true);
    FParse::Value(Cmd, TEXT("BenchOut="), B.OutDir);
    B.bProfileGpu = !FParse::Param(Cmd, TEXT("BenchNoProfileGPU"));
    B.bCsv = FParse::Param(Cmd, TEXT("BenchCsv"));
    FString Fixture = FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), TEXT("S08BenchCobble.json"));
    FParse::Value(Cmd, TEXT("BenchFixture="), Fixture);
    if (B.OutDir.IsEmpty() || B.Views.Num() == 0) {
      Finish(TEXT("BENCH FAILED usage: -BenchOut=<dir> and -BenchViews=K1+K2x5 are required"));
      return;
    }
    FS08Snapshot Snap;
    TSharedPtr<FJsonObject> Root;
    if (!S08LoadGameStateFixture(Fixture, Snap, &Root) || !Root.IsValid()) {
      Finish(FString::Printf(TEXT("BENCH FAILED fixture load %s"), *Fixture));
      return;
    }
    Root->TryGetStringField(TEXT("benchViewerId"), BenchViewerId);
    Root->TryGetStringField(TEXT("benchBoardId"), BenchBoardId);
    if (!FS08BoardModel::DecodeFighters(Snap.Fighters, Fighters) || !BoardModel.Decode(Snap.BoardState)) {
      Finish(TEXT("BENCH FAILED fighters/board decode"));
      return;
    }
    for (const FS08BoardFighter& F : Fighters) {
      if (F.OwnerId == BenchViewerId && F.bIsHero) B.HeroId = F.Id;
    }
    float Fps = 0.0f;
    FParse::Value(Cmd, TEXT("BenchFps="), Fps);
    S08BenchSetCvar(TEXT("t.MaxFPS"), FString::SanitizeFloat(Fps));
    S08BenchSetCvar(TEXT("r.VSync"), TEXT("0"));
    S08BenchSetCvar(TEXT("r.ProfileGPU.ShowUI"), TEXT("0"));
    SyncBoardFromApplied();
    FS08Trace::Write(FString::Printf(
        TEXT("BENCH scene fixture=%s board=%dx%d fighters=%d viewer=%s hero=%s art=%d profile=%s views=%s warmup=%.0f settle=%.0f measure=%.0f fps=%.0f profileGpu=%d csv=%d"),
        *FPaths::GetCleanFilename(Fixture), BoardModel.Width, BoardModel.Height, Fighters.Num(),
        *BenchViewerId, B.HeroId.IsEmpty() ? TEXT("-") : *B.HeroId,
        BoardActor && BoardActor->IsArtActive() ? 1 : 0,
        BoardActor && !BoardActor->GetArtProfileId().IsEmpty() ? *BoardActor->GetArtProfileId() : TEXT("-"),
        *Views, B.Warmup, B.Settle, B.Measure, Fps, B.bProfileGpu ? 1 : 0, B.bCsv ? 1 : 0));
    B.Step = 1;
    B.NextAt = Elapsed + B.Warmup;
    return;
  }
  const FString View = B.Views.IsValidIndex(B.View) ? B.Views[B.View] : FString();
  switch (B.Step) {
    case 1:  // warm-up (shader/PSO caches, Lumen surface cache and history)
      if (Elapsed < B.NextAt) return;
      FS08Trace::Write(FString::Printf(TEXT("BENCH warmup done elapsed=%.1f"), Elapsed));
      B.Step = 2;
      return;
    case 2: {  // view setup
      const float Zoom = S08BenchViewZoom(View);
      // ENV-U9: a "K1..." view never selects the hero (centred on the board); "K2..." focuses it.
      const bool bCentredView = View.StartsWith(TEXT("K1"));
      if (Zoom > 1.0f && !bCentredView && !B.HeroId.IsEmpty()) {
        SelectFighter(B.HeroId);
        const FS08ZoomStep ZoomStep = CameraZoom.FocusZoom(Zoom);
        FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s focus hero=%s zoom=%.2f target=%.1f clamp=%d"), *View,
                                         *B.HeroId, Zoom, ZoomStep.To, ZoomStep.bClamped ? 1 : 0));
      } else if (Zoom > 1.0f && bCentredView) {
        // "K1x1.25": nothing selected, so the follow rig (>= 1.2x) has no target and the focus stays at the centre.
        SelectFighter(FString());
        const FS08ZoomStep ZoomStep = CameraZoom.FocusZoom(Zoom);
        FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s centred zoom=%.2f target=%.1f fit=%.1f clamp=%d"), *View,
                                         Zoom, ZoomStep.To, CameraZoom.Fit, ZoomStep.bClamped ? 1 : 0));
      } else if (Zoom > 0.0f && Zoom < 1.0f) {
        // ENV-MAPS "K1x0.65": zoom-out from the overview by wheel notches (the
        // player's own path), stopping at the requested zoom or the far limit
        // (fit / OverviewOutRatio: 0.65x of the overview on grids, 0.8125x =
        // 2880.2 uu = one notch on the ENV-U9 map boards).
        SelectFighter(FString());
        FS08ZoomStep ZoomStep = CameraZoom.ReturnToOverview();
        const float Wanted = CameraZoom.Overview / Zoom;
        for (int32 Notch = 0; Notch < 16 && CameraZoom.Target < Wanted - 0.5f && ZoomStep.Limit != ES08ZoomLimit::Far;
             ++Notch) {
          ZoomStep = CameraZoom.Wheel(-1);
        }
        FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s zoom-out wanted=%.2f target=%.1f zoom=%.2f limit=%s"),
                                         *View, Zoom, CameraZoom.Target, CameraZoom.ZoomOf(CameraZoom.Target),
                                         S08ZoomLimitName(ZoomStep.Limit)));
      } else {
        SelectFighter(FString());
        CameraZoom.ReturnToOverview();
        FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s overview target=%.1f fit=%.1f"), *View, CameraZoom.Target,
                                         CameraZoom.Fit));
      }
      B.StepStart = Elapsed;
      B.bSettleLogged = false;
      B.Step = 3;
      return;
    }
    case 3: {  // camera settle, then a Lumen / TSR history settle
      const float DistErrPct = CameraZoom.Target > 0.0f
          ? 100.0f * FMath::Abs(CameraZoom.Current - CameraZoom.Target) / CameraZoom.Target : 100.0f;
      const float FocusErr = FVector::Dist(CameraZoom.CurrentFocus, CameraZoom.TargetFocus);
      const bool bSettled = DistErrPct < 1.0f && FocusErr < 1.0f;
      if (!bSettled && Elapsed - B.StepStart < 20.0f) return;
      if (!B.bSettleLogged) {
        B.bSettleLogged = true;
        B.NextAt = Elapsed + B.Settle;
        FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s camera settled=%d dist=%.1f target=%.1f zoom=%.2f"),
                                         *View, bSettled ? 1 : 0, CameraZoom.Current, CameraZoom.Target,
                                         CameraZoom.ZoomOf(CameraZoom.Current)));
      }
      if (Elapsed < B.NextAt) return;
      B.FrameMs.Reset();
      B.GpuMs.Reset();
      B.GameMs.Reset();
      B.RenderMs.Reset();
      if (B.bCsv && GEngine) GEngine->Exec(GetWorld(), TEXT("CsvProfile Start"));
      B.StepStart = Elapsed;
      B.Step = 4;
      return;
    }
    case 4:  // measurement window
      B.FrameMs.Add(static_cast<float>(FApp::GetDeltaTime() * 1000.0));
      B.GpuMs.Add(static_cast<float>(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles())));
      B.GameMs.Add(static_cast<float>(FPlatformTime::ToMilliseconds(GGameThreadTime)));
      B.RenderMs.Add(static_cast<float>(FPlatformTime::ToMilliseconds(GRenderThreadTime)));
      if (Elapsed - B.StepStart < B.Measure) return;
      if (B.bCsv && GEngine) GEngine->Exec(GetWorld(), TEXT("CsvProfile Stop"));
      FS08Trace::Write(FString::Printf(TEXT("BENCH measure view=%s window=%.1f %s"), *View, Elapsed - B.StepStart,
                                       *S08PerfStats(B.FrameMs, B.GpuMs, B.GameMs, B.RenderMs)));
      FS08Trace::Write(S08RenderFingerprint(
          GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(), TEXT("BENCH")));
      if (B.bProfileGpu && GEngine) {
        GEngine->Exec(GetWorld(), TEXT("ProfileGPU"));
        FS08Trace::Write(FString::Printf(TEXT("BENCH profilegpu view=%s requested (dump in Unmatched.log, LogRHI)"), *View));
      }
      B.NextAt = Elapsed + 3.0f;
      B.Step = 5;
      return;
    case 5:  // shot (after the ProfileGPU frame)
      if (Elapsed < B.NextAt) return;
      B.ShotPath = FPaths::Combine(B.OutDir, FString::Printf(TEXT("bench-%s-1920x1080.png"),
                                                             *View.Replace(TEXT("."), TEXT("p"))));
      TakeEvidenceShot(B.ShotPath);
      B.NextAt = Elapsed + 15.0f;
      B.Step = 6;
      return;
    case 6:
      if (!FPaths::FileExists(B.ShotPath) && Elapsed < B.NextAt) return;
      FS08Trace::Write(FString::Printf(TEXT("BENCH shot view=%s saved=%d path=%s"), *View,
                                       FPaths::FileExists(B.ShotPath) ? 1 : 0, *B.ShotPath));
      ++B.View;
      if (B.View < B.Views.Num()) {
        B.Step = 2;
        return;
      }
      Finish(FString::Printf(TEXT("BENCH done views=%d elapsed=%.1f"), B.Views.Num(), Elapsed));
      return;
    default:
      return;
  }
}

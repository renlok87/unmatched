#include "S08FlowGameMode.h"
#include "S08BoardActor.h"
#include "S08FighterActor.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "HAL/PlatformMisc.h"
#include "Misc/FileHelper.h"
#include "ImageUtils.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Paths.h"
#include "S08TraceLog.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/CoreStyle.h"

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
  Flow->OnStage.AddLambda([this](ES08Stage) { RefreshUi(); });
  Flow->OnRoom.AddLambda([this](const FS08RoomState&) { RefreshUi(); });
  Flow->OnFlowError.AddLambda([this](const FS08GraphQLError& Error) {
    TraceLines.Add(TEXT("[error] ") + Error.Code + TEXT(": ") + Error.Message);
    RefreshUi();
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

  FS08Trace::Open();
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
        Flow->CreateRoom(TEXT("ONE_V_ONE"));
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
        const bool AllReady = Room.Players.Num() == 2 &&
                              Room.Players[0].bIsReady && Room.Players[1].bIsReady;
        const bool BothHeroes = Room.Players.Num() == 2 && !Room.Players[0].HeroId.IsEmpty() &&
                                !Room.Players[1].HeroId.IsEmpty();
        if (AllReady && BothHeroes) {
          Flow->StartGame();
          ++AutoStep;
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

void AS08FlowGameMode::SyncBoardFromApplied() {
  if (!BoardActor) {
    FActorSpawnParameters Params;
    Params.Owner = this;
    BoardActor = GetWorld()->SpawnActor<AS08BoardActor>(
        AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, Params);
    if (BoardActor) {
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
    }
  } else {
    BoardActor->Rebuild(BoardModel);
  }
  if (BoardActor) {
    BoardActor->SyncFighters(BoardModel, Fighters, Flow->GetUserId());
    // GD-030 six-fighter evidence line: the projection's roster, split into
    // own/enemy for THIS viewer (asserted by the demo driver; the image
    // checker alone cannot count silhouettes).
    int32 Alive = 0, Own = 0, Enemy = 0;
    for (const FS08BoardFighter& F : Fighters) {
      if (!F.IsAlive()) continue;
      ++Alive;
      if (F.OwnerId == Flow->GetUserId()) ++Own; else ++Enemy;
    }
    FS08Trace::Write(FString::Printf(TEXT("FIGHTERS synced n=%d alive=%d own=%d enemy=%d"),
                                     Fighters.Num(), Alive, Own, Enemy));
    // Selection survived the update: recompute reachability from fresh data.
    if (!SelectedFighterId.IsEmpty()) {
      SelectFighter(SelectedFighterId);
    }
  }
  RefreshUi();
}

void AS08FlowGameMode::SetupCameraForBoard() {
  if (!GetWorld()) return;
  // Fit the whole board (any W/H) at FOV 35, pitch -55, yaw -90 (INT-019:
  // camera looks along -Y, row y=0 far/north). UE's FOVAngle is the
  // HORIZONTAL fov: derive the vertical half-tan by dividing by the aspect
  // (treating it as vertical shrinks the real vertical fov to ~20 degrees
  // and the near board corner with its fighters falls out of frame).
  const float Hfov = 35.0f;
  const float Aspect = 16.0f / 9.0f;
  const float HalfH = FMath::Tan(FMath::DegreesToRadians(Hfov * 0.5f));
  const float HalfV = HalfH / Aspect;
  const float ExtentY = BoardModel.Height * FS08BoardModel::CellSizeUU * 0.5f;
  const float ExtentX = BoardModel.Width * FS08BoardModel::CellSizeUU * 0.5f;
  // Vertical screen span covers the board's Y extent tilted by the pitch.
  const float SinPitch = FMath::Sin(FMath::DegreesToRadians(55.0f));
  const float CosPitch = FMath::Cos(FMath::DegreesToRadians(55.0f));
  const float NeedV = (ExtentY * SinPitch + 60.0f) / HalfV;
  const float NeedH = (ExtentX + 60.0f) / HalfH;
  const float Distance = FMath::Max(NeedV, NeedH) * 1.12f;
  const FVector Location(0.0f, Distance * CosPitch, Distance * SinPitch);

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

  if (PC->WasInputKeyJustPressed(EKeys::RightMouseButton)) {
    SelectedFighterId.Reset();
    ReachableCells.Reset();
    BoardActor->ClearSelection();
    return;
  }
  if (!PC->WasInputKeyJustPressed(EKeys::LeftMouseButton)) return;

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
    Toast = TEXT("click outside the board - ignored");
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
    bAwaitManeuverFinish = true;
    Flow->BeginManeuver();         // submit leg runs from Tick once pending exists
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
  Flow->SubmitManeuver(PendingId, Moves);
}

// ---- demo drive ----------------------------------------------------------

void AS08FlowGameMode::RunAutoManeuver() {
  if (!Flow.IsValid() || !BoardActor) return;
  // Pick the own hero; move one orthogonal step to a legal adjacent cell.
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
  static const int32 Dx[4] = {1, -1, 0, 0};
  static const int32 Dy[4] = {0, 0, 1, -1};
  for (int32 Dir = 0; Dir < 4; ++Dir) {
    const int32 NX = Hero->X + Dx[Dir];
    const int32 NY = Hero->Y + Dy[Dir];
    if (Reachable.Contains(FS08BoardModel::CellKey(NX, NY))) {
      TargetX = NX;
      TargetY = NY;
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

void AS08FlowGameMode::TakeEvidenceShot() {
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
  }
  // SceneCapture fallback: renders the board through an explicit capture
  // component (independent of the viewport), then writes the PNG directly.
  // Used when the HighResShot viewport path comes out black.
  if (BoardCamera) {
    UCameraComponent* CamComp = BoardCamera->GetCameraComponent();
    if (CamComp) {
      USceneCaptureComponent2D* Capture =
          NewObject<USceneCaptureComponent2D>(BoardCamera);
      Capture->SetupAttachment(CamComp);
      Capture->RegisterComponent();
      Capture->bCaptureEveryFrame = false;
      Capture->bCaptureOnMovement = false;
      Capture->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
      Capture->FOVAngle = CamComp->FieldOfView;
      Capture->ShowFlags.SetAtmosphere(false);
      Capture->ShowFlags.SetFog(false);
      UTextureRenderTarget2D* Target =
          NewObject<UTextureRenderTarget2D>(Capture);
      Target->InitAutoFormat(1920, 1080);
      Capture->TextureTarget = Target;
      Capture->CaptureScene();
      FTextureRenderTargetResource* Res =
          Capture->TextureTarget ? Capture->TextureTarget->GameThread_GetRenderTargetResource()
                                 : nullptr;
      if (Res) {
        FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
        TArray<FColor> Pixels;
        if (Res->ReadPixels(Pixels, ReadFlags)) {
          const int32 Width = Res->GetSizeX();
          const int32 Height = Res->GetSizeY();
          TArray<uint8> Png;
          FImageUtils::CompressImageArray(Width, Height, Pixels, Png);
          FString CapPath = AutoShotPath.IsEmpty()
                                ? FPaths::ProjectSavedDir() / TEXT("S08SceneCapture.png")
                                : AutoShotPath.Replace(TEXT(".png"), TEXT("-capture.png"));
          if (FFileHelper::SaveArrayToFile(Png, *CapPath)) {
            FS08Trace::Write(FString::Printf(TEXT("SHOT capture saved %s (%dx%d)"), *CapPath,
                                             Width, Height));
          }
        }
      }
      Capture->UnregisterComponent();
      Capture->DestroyComponent();
    }
  }
  // Memory note: the HighResShot exec renders 1920x1080 offscreen reliably
  // (hidden window included). The output path MUST ride on filename= - a bare
  // quoted path token is silently ignored and both packaged clients sharing
  // one staged Saved dir overwrite each other's HighresScreenshot00000.png.
  FString Command = TEXT("HighResShot 1920x1080");
  if (!AutoShotPath.IsEmpty()) {
    Command += TEXT(" filename=\"") + AutoShotPath + TEXT("\"");
  }
  UKismetSystemLibrary::ExecuteConsoleCommand(GetWorld(), Command, PC);
  const FString Line = TEXT("SHOT requested: HighResShot 1920x1080");
  TraceLines.Add(Line);
  FS08Trace::Write(Line);
}

void AS08FlowGameMode::Tick(float DeltaSeconds) {
  Super::Tick(DeltaSeconds);
  Elapsed += DeltaSeconds;
  PollAccumulator += DeltaSeconds;
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
  if (ToastUntil > 0.0f && Elapsed > ToastUntil) {
    ToastUntil = 0.0f;
    Toast.Reset();
    RefreshUi();
  }
  if (IllegalUntil > 0.0f && Elapsed > IllegalUntil) {
    IllegalUntil = 0.0f;
    if (BoardActor) BoardActor->HideIllegalCell();
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
      TakeEvidenceShot();
    }
  }
  if (AutoExitAfter > 0.0f && Elapsed > AutoExitAfter) {
    UE_LOG(LogTemp, Display, TEXT("S08_FLOW_COMPLETE elapsed=%f"), Elapsed);
    FS08Trace::Close();
    FGenericPlatformMisc::RequestExit(false);
  }
}

void AS08FlowGameMode::EndPlay(const EEndPlayReason::Type Reason) {
  FS08Trace::Close();
  if (Flow.IsValid()) Flow.Reset();
  Super::EndPlay(Reason);
}

void AS08FlowGameMode::BuildUi() {
  if (!GEngine || !GEngine->GameViewport) return;

  TSharedRef<SVerticalBox> Root = SNew(SVerticalBox);
  Root->AddSlot().AutoHeight()
      [SNew(STextBlock).Text(FText::FromString(TEXT("UNMATCHED S08 grey flow (GD-028..031)")))
           .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))];

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
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("CREATE ROOM (ONE_V_ONE)")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid()) Flow->CreateRoom(TEXT("ONE_V_ONE"));
             return FReply::Handled();
           })];
  TSharedRef<SEditableTextBox> CodeRef = SNew(SEditableTextBox);
  CodeBox = CodeRef;
  Root->AddSlot().AutoHeight()
      .Padding(4)[SNew(SHorizontalBox) +
                  SHorizontalBox::Slot().AutoWidth()
                      [SNew(STextBlock).Text(FText::FromString(TEXT("room code: ")))] +
                  SHorizontalBox::Slot().FillWidth(0.2f)[CodeRef]];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("JOIN BY CODE")))
           .OnClicked_Lambda([this]() {
             if (Flow.IsValid() && CodeBox.IsValid()) {
               Flow->JoinRoomByCode(CodeBox.Pin()->GetText().ToString().TrimStartAndEnd());
             }
             return FReply::Handled();
           })];
  Root->AddSlot().AutoHeight().Padding(4)
      [SNew(SButton).Text(FText::FromString(TEXT("RECOVER MY ROOM (myGames)")))
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

  GEngine->GameViewport->AddViewportWidgetContent(Root, 0);
}

void AS08FlowGameMode::RefreshUi() {
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

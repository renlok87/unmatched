// VS-7 S1 (docs/game-design/visual/05-production-plan.md §3 VS-7; screens.csv SC-02...SC-07): the game-mode side of the
// menu backdrop (UI/UmMenuBackdrop.h) and of the BOOT / LOGIN screens (UI/UmScreenBoot.h, UI/UmScreenLogin.h).
//
//   screens   built once at BeginPlay (the backend flow only - never for -Bench, -S09HudProbe, the galleries) into the
//             root's Screens switcher; the active child follows the flow: BOOT (stage Boot for 1 s - no stored session,
//             GD-038 - then LOGIN; after the login the catalogue pass heroes -> boards -> the own live match), LOGIN
//             (stage Boot after the session stage, Failed: a refused login or an expired session), otherwise the GAME
//             screen as before. The legacy Slate flow panel hides while a UMG route screen covers it (F10 still forces
//             it - and then the UMG screens step aside). -S08Auto runs keep their drive: BOOT shows, LOGIN and the
//             catalogue pass do not (no second heroList, no resume modal over an auto room).
//   backdrop  SC-02: the Marmoreal K1 scene without figures from BOOT on; handed over to the match board (or swapped)
//             at the first snapshot, built again once the match board is gone.
//   evidence  review tooling: -S08MenuDrive=<bg+login+badpass+retry+resume|lobby+server+exit> drives the screens through
//             their states with the credentials of the process environment (S08_EMAIL / S08_PASSWORD - never argv,
//             never traced); with -S08ScreenShots and -S09ShotDir one frame per sub-state
//             UI-SCR-BOOT-<loading-session|loading-heroes-wait|loading-heroes|loading-boards|error|retrying|resume|resuming>.png,
//             UI-SCR-LOGIN-<empty|input|busy|error-credentials|error-server>.png and menu-bg.png (the scene without UI).
#include "S08FlowGameMode.h"

#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08TraceLog.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmMenuBackdrop.h"
#include "UI/UmScreenBoot.h"
#include "UI/UmScreenLobby.h"
#include "UI/UmScreenLogin.h"
#include "UI/UmSpinner.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/WidgetSwitcher.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

/** Per-run state of the VS-7 route screens and the menu backdrop (owned by the game mode). */
struct FUmFlowScreensRuntime {
  S08ArtLook::FS08SlateHudBlocks Blocks;
  TWeakObjectPtr<UUmScreenBoot> Boot;
  TWeakObjectPtr<UUmScreenLogin> Login;
  TWeakObjectPtr<UWidget> GameChild;  // the GAME screen's child of Screens (restored when no route screen shows)
  FIntPoint LastCanvas = FIntPoint(-1, -1);
  float LastPxPerSu = -1.0f;
  bool LastClassS = false;
  // SC-02
  bool bBackdrop = false;
  TWeakObjectPtr<AS08BoardActor> MenuBoard;
  FS08BoardModel MenuModel;
  FString MenuBoardId;
  bool bMenuModel = false;
  bool bMenuFailed = false;
  FString LastBgKey;
  // BOOT
  FUmBootModel Model;
  double BootShownAtMs = -1.0;
  double StageStartMs = -1.0;
  double PassedAtMs = -1.0;
  int32 HeroFailSeen = 0;
  bool bRequested = false;
  bool bPassDone = false;
  bool bLogoPlayed = false;
  bool bNetLostPlayed = false;
  bool bResumeOpenPlayed = false;
  ES08Stage LastStage = ES08Stage::Boot;
  // which route screen shows ("" none / boot / login)
  FString Showing;
  // evidence
  int32 Shots = -1;
  TSet<FString> ShotKeys;
  FString Drive;
  int32 DriveStep = 0;
  double DriveAtMs = -1.0;
  bool bBgHidden = false;
};

namespace {
double UmFsNowMs() { return FPlatformTime::Seconds() * 1000.0; }

const TCHAR* UmFsStageName(ES08Stage S) {
  switch (S) {
    case ES08Stage::Boot: return TEXT("Boot");
    case ES08Stage::Login: return TEXT("Login");
    case ES08Stage::Lobby: return TEXT("Lobby");
    case ES08Stage::Room: return TEXT("Room");
    case ES08Stage::Started: return TEXT("Started");
    default: return TEXT("Failed");
  }
}

bool UmFsHas(const FString& Plan, const TCHAR* Token) {
  TArray<FString> Parts;
  Plan.ParseIntoArray(Parts, TEXT("+"), true);
  return Parts.Contains(FString(Token));
}

FString UmFsHeroName(const TArray<FS08HeroEntry>& Heroes, const FString& HeroId) {
  const FS08HeroEntry* H = Heroes.FindByPredicate([&HeroId](const FS08HeroEntry& E) { return E.Id == HeroId; });
  return H ? H->Name : FString();
}
}  // namespace

// ------------------------------------------------------------------------------------------------ build

void AS08FlowGameMode::BuildUmFlowScreens() {
  if (!UmFlowScreens.IsValid()) UmFlowScreens = MakeShared<FUmFlowScreensRuntime>();
  FUmFlowScreensRuntime& R = *UmFlowScreens;
  R.Blocks = S08ArtLook::SlateHudBlocks();
  R.Model.BuildCommit = UmBoot::BuildCommit();
  FParse::Value(FCommandLine::Get(), TEXT("S08MenuDrive="), R.Drive);
  // SC-02: the menu backdrop (built in the first tick, after the viewport exists)
  R.bBackdrop = UmMenuBackdrop::Wanted(R.Blocks);
  if (!R.bBackdrop) {
    FS08Trace::Write(UmMenuBackdrop::TraceLine(FString(), FString(), 0, FString(), UmFsStageName(Flow.IsValid() ? Flow->GetStage() : ES08Stage::Boot),
                                               TEXT("off")) + TEXT(" reason=-S08SlateHud"));
  }
  if (!UmHudRoot || !UmHudRoot->Screens || !R.Blocks.UmgRoot()) {
    FS08Trace::Write(TEXT("HUD-SCREENS boot=slate login=slate reason=no-umg-root"));
    return;
  }
  R.GameChild = UmHudRoot->Screens->GetActiveWidget();
  const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  if (!R.Blocks.IsSlate(FName(TEXT("boot")))) {
    if (UUmScreenBoot* B = CreateWidget<UUmScreenBoot>(UmHudRoot, UUmScreenBoot::WidgetClass())) {
      UmHudRoot->Screens->AddChild(B);
      UUmScreenBoot::FInput In;
      In.OnRetry = [WeakThis]() {
        AS08FlowGameMode* Self = WeakThis.Get();
        if (!Self || !Self->UmFlowScreens.IsValid()) return;
        FUmFlowScreensRuntime& S = *Self->UmFlowScreens;
        Self->PlayScreenSound(FName(TEXT("UI-BTN-CLICK")));
        S.Model.bRetrying = true;  // the banner stays; «Повторить» waits with why.syncing
        S.bRequested = false;      // the current stage asks again
        FS08Trace::Write(FString::Printf(TEXT("BOOT retry stage=%s"), UmBoot::StageName(S.Model.Stage)));
      };
      In.OnResume = [WeakThis]() {
        AS08FlowGameMode* Self = WeakThis.Get();
        if (!Self || !Self->UmFlowScreens.IsValid() || !Self->Flow.IsValid()) return;
        Self->PlayScreenSound(FName(TEXT("UI-CONFIRM")));
        Self->UmFlowScreens->Model.bResuming = true;
        FS08Trace::Write(FString::Printf(TEXT("BOOT resume game=%s"), *Self->Flow->GetActiveGame().GameId));
        if (!Self->Flow->ResumeActiveGame()) {
          Self->UmFlowScreens->Model.bResuming = false;
          FS08Trace::Write(TEXT("BOOT resume refused"));
        }
      };
      In.OnLobby = [WeakThis]() {
        AS08FlowGameMode* Self = WeakThis.Get();
        if (!Self || !Self->UmFlowScreens.IsValid()) return;
        Self->PlayScreenSound(FName(TEXT("UI-BTN-CLICK")));
        Self->UmFlowScreens->Model.bResume = false;
        Self->UmFlowScreens->bPassDone = true;  // the match stays on the server (no leave)
        FS08Trace::Write(TEXT("BOOT resume declined: lobby, the match stays IN_PROGRESS"));
      };
      B->SetInput(HudPress, MoveTemp(In));
      R.Boot = B;
    }
  }
  if (!R.Blocks.IsSlate(FName(TEXT("login")))) {
    if (UUmScreenLogin* L = CreateWidget<UUmScreenLogin>(UmHudRoot, UUmScreenLogin::WidgetClass())) {
      UmHudRoot->Screens->AddChild(L);
      UUmScreenLogin::FInput In;
      In.OnSubmit = [WeakThis](const FString& Email, const FString& Password) {
        AS08FlowGameMode* Self = WeakThis.Get();
        if (!Self || !Self->Flow.IsValid()) return;
        FS08Trace::Write(TEXT("LOGIN submit source=umg"));  // never the email or the password
        Self->Flow->Login(Email, Password);
      };
      In.OnSound = [WeakThis](FName Bank) {
        if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
      };
      L->SetInput(HudPress, MoveTemp(In));
      R.Login = L;
    }
  }
  if (Flow.IsValid()) {
    Flow->OnFlowError.AddLambda([WeakThis](const FS08GraphQLError& Error) {
      if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmFlowLoginError(Error);
    });
  }
  BuildUmLobby();  // VS-7 S2: LOBBY SC-08...SC-13 (S08FlowGameModeUmLobby.cpp)
  FString BootMissing, LoginMissing;
  FS08Trace::Write(FString::Printf(TEXT("HUD-SCREENS boot=%s login=%s bootParts=%d loginParts=%d missing=%s drive=%s"),
                                   R.Boot.IsValid() ? *R.Boot->SourceName() : TEXT("slate"),
                                   R.Login.IsValid() ? *R.Login->SourceName() : TEXT("slate"),
                                   R.Boot.IsValid() && R.Boot->HasAllParts(&BootMissing) ? 1 : 0,
                                   R.Login.IsValid() && R.Login->HasAllParts(&LoginMissing) ? 1 : 0,
                                   (BootMissing + LoginMissing).IsEmpty() ? TEXT("-") : *(BootMissing + TEXT(" ") + LoginMissing),
                                   R.Drive.IsEmpty() ? TEXT("-") : *R.Drive));
}

void AS08FlowGameMode::HandleUmFlowLoginError(const FS08GraphQLError& Error) {
  if (!UmFlowScreens.IsValid()) return;
  UUmScreenLogin* L = UmFlowScreens->Login.Get();
  if (!L || !L->IsBusy()) return;  // only the answer of a login this screen sent
  const EUmLoginError E = UmLogin::ClassifyError(Error.Code);
  FS08Trace::Write(FString::Printf(TEXT("LOGIN error code=%s shown=%s"), *Error.Code, UmLogin::ErrorName(E)));
  L->ShowError(E);
}

bool AS08FlowGameMode::UmFlowScreensCoverLegacy() const {
  return UmFlowScreens.IsValid() && !UmFlowScreens->Showing.IsEmpty();
}

bool AS08FlowGameMode::UmFlowScreensBusy() const {
  if (!UmFlowScreens.IsValid()) return false;
  const FUmFlowScreensRuntime& R = *UmFlowScreens;
  if (R.Showing == TEXT("login") && R.Login.IsValid() && R.Login->IsBusy()) return true;
  if (R.Showing == TEXT("lobby") && GetUmLobby() && GetUmLobby()->IsBusy()) return true;
  return R.Showing == TEXT("boot") && (R.Model.bResuming || R.Model.bRetrying);
}

// ------------------------------------------------------------------------------------------------ SC-02 backdrop

AS08BoardActor* AS08FlowGameMode::UmMenuBackdropHandOver(const FString& RoomBoardId) {
  if (!UmFlowScreens.IsValid()) return nullptr;
  FUmFlowScreensRuntime& R = *UmFlowScreens;
  AS08BoardActor* Menu = R.MenuBoard.Get();
  R.MenuBoard.Reset();
  if (!Menu) return nullptr;
  const TCHAR* Stage = UmFsStageName(Flow.IsValid() ? Flow->GetStage() : ES08Stage::Started);
  const FString Backdrop = S08ArtLook::BackdropField(Menu->GetConceptPasteSpec(), Menu->GetConceptPasteMode());
  if (RoomBoardId == R.MenuBoardId) {
    // Marmoreal: the same actors become the match board; the fighters come from the snapshot (no second copy)
    FS08Trace::Write(UmMenuBackdrop::TraceLine(R.MenuBoardId, Menu->GetArtProfileId(), 0, Backdrop, Stage, TEXT("handover")));
    R.LastBgKey = TEXT("handover");
    return Menu;
  }
  // another board (Sarpedon): the menu board goes in the frame the match board spawns (the swap under the loading)
  FS08Trace::Write(UmMenuBackdrop::TraceLine(R.MenuBoardId, Menu->GetArtProfileId(), 0, Backdrop, Stage, TEXT("swap")) +
                   FString::Printf(TEXT(" to=%s"), RoomBoardId.IsEmpty() ? TEXT("-") : *RoomBoardId));
  R.LastBgKey = TEXT("swap");
  Menu->Destroy();
  return nullptr;
}

namespace {
/** The K1 overview camera of SetupCameraForBoard for a board actor (pitch -55, yaw -90, FOV 35), without its traces. */
FVector UmFsK1Location(const AS08BoardActor& Board, float& OutDistance, float& OutFit) {
  OutFit = S08K1FitDistanceUU(Board.GetBoardHalfExtentUU());
  OutDistance = S08K1OverviewDistanceUU(OutFit, Board.GetK1DistanceMul());
  const float Pitch = FMath::DegreesToRadians(55.0f);
  return FVector(0.0f, OutDistance * FMath::Cos(Pitch), OutDistance * FMath::Sin(Pitch));
}
}  // namespace

static void UmFsTickBackdrop(AS08FlowGameMode& GM, FUmFlowScreensRuntime& R, ES08Stage Stage, UWorld* World,
                             TObjectPtr<AS08BoardActor>& MatchBoard, TObjectPtr<ACameraActor>& Camera, FS08CameraZoom& Zoom) {
  if (!R.bBackdrop || !World) return;
  const TCHAR* StageName = UmFsStageName(Stage);
  // the match board owns the scene once it exists (the first snapshot); the menu board comes back when it is gone
  if (MatchBoard) return;
  AS08BoardActor* Menu = R.MenuBoard.Get();
  if (!Menu) {
    if (R.bMenuFailed) return;
    if (!R.bMenuModel) {
      FString Problem;
      R.bMenuModel = UmMenuBackdrop::LoadBoard(UmMenuBackdrop::FixturePath(), R.MenuModel, R.MenuBoardId, &Problem);
      if (!R.bMenuModel) {
        R.bMenuFailed = true;
        FS08Trace::Write(UmMenuBackdrop::TraceLine(FString(), FString(), 0, FString(), StageName, TEXT("off")) +
                         TEXT(" reason=fixture ") + Problem);
        return;
      }
      if (R.MenuBoardId.IsEmpty()) R.MenuBoardId = UmMenuBackdrop::BoardId;
    }
    FActorSpawnParameters Params;
    Params.Owner = &GM;
    Menu = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, Params);
    if (!Menu) {
      R.bMenuFailed = true;
      return;
    }
    // the same path as a match board (SyncBoardFromApplied / -Bench): the room board id picks the art profile
    Menu->SetRoomBoardId(R.MenuBoardId);
    Menu->Rebuild(R.MenuModel);
    R.MenuBoard = Menu;
    R.LastBgKey.Reset();
    // the K1 camera on BoardCamera (the view target the match keeps) and the zoom rig at its overview
    float Distance = 0.0f, Fit = 0.0f;
    const FVector Location = UmFsK1Location(*Menu, Distance, Fit);
    Zoom.Config = FS08CameraZoomConfig();
    Zoom.Config.ApplyIni(GGameIni);
    Zoom.Config.ApplyCommandLine(FCommandLine::Get());
    Zoom.Config.Sanitize();
    Zoom.Reset(Distance, Fit);
    if (!Camera) {
      FActorSpawnParameters CamParams;
      CamParams.Owner = &GM;
      Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), Location, FRotator(-55.0f, -90.0f, 0.0f), CamParams);
      if (Camera) Camera->GetCameraComponent()->SetFieldOfView(35.0f);
    } else {
      Camera->SetActorLocationAndRotation(Location, FRotator(-55.0f, -90.0f, 0.0f));
    }
    if (APlayerController* PC = World->GetFirstPlayerController()) {
      if (Camera) PC->SetViewTarget(Camera);
      PC->bShowMouseCursor = true;
    }
  }
  const FString Key = FString::Printf(TEXT("menu|%s|%s"), StageName, *Menu->GetArtProfileId());
  if (Key != R.LastBgKey) {
    R.LastBgKey = Key;
    FS08Trace::Write(UmMenuBackdrop::TraceLine(R.MenuBoardId, Menu->GetArtProfileId(), 0,
                                               S08ArtLook::BackdropField(Menu->GetConceptPasteSpec(), Menu->GetConceptPasteMode()),
                                               StageName, TEXT("menu")));
  }
}

// ------------------------------------------------------------------------------------------------ tick

void AS08FlowGameMode::TickUmFlowScreens() {
  if (!UmFlowScreens.IsValid() || !Flow.IsValid()) return;
  FUmFlowScreensRuntime& R = *UmFlowScreens;
  const double Now = UmFsNowMs();
  const ES08Stage Stage = Flow->GetStage();
  UmFsTickBackdrop(*this, R, Stage, GetWorld(), BoardActor, BoardCamera, CameraZoom);

  // a new login: the catalogue pass runs again; the LOGIN screen forgets the password
  if (Stage != R.LastStage) {
    if (Stage == ES08Stage::Login && R.LastStage != ES08Stage::Login) {
      R.Model.Stage = EUmBootStage::Heroes;
      R.Model.bHeroesLoaded = false;
      R.Model.bError = R.Model.bRetrying = R.Model.bResume = R.Model.bResuming = false;
      R.bRequested = false;
      R.bPassDone = bAuto;  // -S08Auto: the drive goes on by itself (no second heroList, no resume modal)
      R.StageStartMs = R.PassedAtMs = -1.0;
      R.bNetLostPlayed = R.bResumeOpenPlayed = false;
      if (R.Login.IsValid()) R.Login->ResetAfterLogin();
    }
    R.LastStage = Stage;
  }

  // ---- the BOOT pass after the login: heroes -> boards -> the own live match (04 §1.1, SC-03...SC-05)
  if (Stage == ES08Stage::Login && !R.bPassDone && R.Boot.IsValid()) {
    FUmBootModel& M = R.Model;
    auto Fail = [&R, &M, this, Now]() {
      if (!M.bError || M.bRetrying) {
        M.bError = true;
        M.bRetrying = false;
        if (!R.bNetLostPlayed) PlayScreenSound(FName(TEXT("UI-NET-LOST")));
        R.bNetLostPlayed = true;
        FS08Trace::Write(FString::Printf(TEXT("BOOT error stage=%s waited=%.0f"), UmBoot::StageName(M.Stage), Now - R.StageStartMs));
      }
    };
    auto Pass = [&R, &M, Now]() {
      M.bError = M.bRetrying = false;
      if (R.PassedAtMs < 0.0) R.PassedAtMs = Now;
      return Now - R.PassedAtMs >= UmBoot::MinStageMs;
    };
    auto Next = [&R](EUmBootStage S) {
      R.Model.Stage = S;
      R.bRequested = false;
      R.PassedAtMs = -1.0;
    };
    if (M.Stage == EUmBootStage::Heroes) {
      if (!R.bRequested) {
        R.bRequested = true;
        R.StageStartMs = Now;
        R.HeroFailSeen = Flow->GetHeroesFailures();
        if (Flow->GetHeroes().Num() == 0 || M.bRetrying) Flow->FetchHeroes();
      }
      if (Flow->GetHeroes().Num() > 0) {
        M.bHeroesLoaded = true;
        M.Heroes = M.HeroesTotal = Flow->GetHeroes().Num();
        if (Pass()) Next(EUmBootStage::Boards);
      } else if (Flow->GetHeroesFailures() > R.HeroFailSeen || UmBoot::TimedOut(R.StageStartMs, Now)) {
        R.HeroFailSeen = Flow->GetHeroesFailures();
        Fail();
        R.StageStartMs = Now;  // the next timeout counts from here (a retry restarts it too)
      }
    } else if (M.Stage == EUmBootStage::Boards) {
      if (!R.bRequested) {
        R.bRequested = true;
        R.StageStartMs = Now;
        Flow->FetchBoards();
      }
      if (Flow->GetBoardsState() == FS08FlowController::EBootQuery::Done) {
        if (Pass()) Next(EUmBootStage::Done);
      } else if (Flow->GetBoardsState() == FS08FlowController::EBootQuery::Failed || UmBoot::TimedOut(R.StageStartMs, Now)) {
        const bool bNew = !M.bError || M.bRetrying;
        Fail();
        if (bNew) R.StageStartMs = Now;
      }
    } else if (M.Stage == EUmBootStage::Done && !M.bResume) {
      if (!R.bRequested) {
        R.bRequested = true;
        R.StageStartMs = Now;
        Flow->FetchActiveGame();
      }
      const FS08FlowController::EBootQuery Q = Flow->GetActiveGameState();
      if (Q == FS08FlowController::EBootQuery::Done) {
        const FS08RoomState& G = Flow->GetActiveGame();
        if (G.GameId.IsEmpty()) {
          if (Pass()) R.bPassDone = true;  // no live match: the lobby
        } else {
          M.bError = M.bRetrying = false;
          M.bResume = true;
          // database names as they are (nominative, ВР-SC10); the board name of its Board row
          for (const FS08RoomPlayer& P : G.Players) {
            const FString Name = UmFsHeroName(Flow->GetHeroes(), P.HeroId);
            (P.UserId == Flow->GetUserId() ? M.ResumeHero : M.ResumeOpponent) = Name;
          }
          const FString* Board = Flow->GetBoardNames().Find(G.BoardId);
          M.ResumeBoard = Board ? *Board : G.BoardId;
          FS08Trace::Write(FString::Printf(TEXT("BOOT resume shown game=%s mode=%s players=%d board=%s"), *G.GameId, *G.Mode,
                                           G.Players.Num(), *G.BoardId));
        }
      } else if (Q == FS08FlowController::EBootQuery::Failed || UmBoot::TimedOut(R.StageStartMs, Now)) {
        const bool bNew = !M.bError || M.bRetrying;
        Fail();
        if (bNew) R.StageStartMs = Now;
      }
    }
  }
  if (R.Model.bResume && !R.bResumeOpenPlayed) {
    R.bResumeOpenPlayed = true;
    PlayScreenSound(FName(TEXT("UI-PANEL-OPEN")));
  }

  // ---- which route screen shows
  FString Want;
  // the session stage: no stored session (GD-038) - BOOT 1 s, then LOGIN; the evidence drive's 'hold' keeps it 6 s
  // (the textures of the first frames stream in - the frames see the finished scene)
  const double BootMs = UmFsHas(R.Drive, TEXT("hold")) ? 6000.0 : 1000.0;
  if (!bDebugPanelForced) {
    if (Stage == ES08Stage::Boot) {
      if (R.BootShownAtMs < 0.0) R.BootShownAtMs = Now;
      // an -S08Auto run keeps BOOT until its own login answers
      Want = (bAuto || Now - R.BootShownAtMs < BootMs || !R.Login.IsValid()) ? TEXT("boot") : TEXT("login");
    } else if (Stage == ES08Stage::Failed) {
      Want = R.Login.IsValid() ? TEXT("login") : FString();
    } else if (Stage == ES08Stage::Login && !R.bPassDone) {
      Want = TEXT("boot");
    } else if (UmLobbyWanted(R.bPassDone)) {
      Want = TEXT("lobby");
    }
    if (Want == TEXT("boot") && !R.Boot.IsValid()) Want.Reset();
    if (Want == TEXT("login") && !R.Login.IsValid()) Want.Reset();
  }
  if (Want == TEXT("boot") && Stage == ES08Stage::Boot) R.Model.Stage = EUmBootStage::Session;
  if (R.bBgHidden) Want = R.Showing;  // the menu-bg frame keeps the route while the screen is hidden
  if (Want != R.Showing) {
    UUmScreenBoot* B = R.Boot.Get();
    UUmScreenLogin* L = R.Login.Get();
    if (B && Want != TEXT("boot")) B->PlayHide();
    if (L && Want != TEXT("login")) L->PlayHide();
    UUmScreenLobby* Lb = GetUmLobby();
    if (Lb && Want != TEXT("lobby")) Lb->PlayHide();
    UWidget* Active = Want == TEXT("boot")    ? static_cast<UWidget*>(B)
                      : Want == TEXT("login") ? static_cast<UWidget*>(L)
                      : Want == TEXT("lobby") ? static_cast<UWidget*>(Lb)
                                              : R.GameChild.Get();
    if (UmHudRoot && UmHudRoot->Screens && Active) UmHudRoot->Screens->SetActiveWidget(Active);
    if (Want == TEXT("boot") && B) {
      B->PlayShow();
      if (!R.bLogoPlayed) {
        R.bLogoPlayed = true;
        PlayScreenSound(FName(TEXT("UI-BOOT-LOGO")));  // the wordmark appeared (08-screen-audio-hooks)
      }
    }
    if (Want == TEXT("login") && L) {
      L->PlayShow();
      L->OnShown();
    }
    if (Want == TEXT("lobby") && Lb) {
      Lb->PlayShow();
      Lb->OnShown();
    }
    FS08Trace::Write(FString::Printf(TEXT("HUD-SCREEN route=%s stage=%s"), Want.IsEmpty() ? TEXT("game") : *Want, UmFsStageName(Stage)));
    R.Showing = Want;
    UpdateLegacyRootVisibility();
  }
  // the canvas of the window (su), the class and px per su
  const FUmHudScaleState& Scale = UmHudScale::Current();
  if (Scale.CanvasSu.X > 0 && (Scale.CanvasSu != R.LastCanvas || Scale.PxPerSu() != R.LastPxPerSu || Scale.bClassS != R.LastClassS)) {
    R.LastCanvas = Scale.CanvasSu;
    R.LastPxPerSu = Scale.PxPerSu();
    R.LastClassS = Scale.bClassS;
    const FVector2D Canvas(Scale.CanvasSu.X, Scale.CanvasSu.Y);
    if (R.Boot.IsValid()) R.Boot->ApplyCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
    if (R.Login.IsValid()) R.Login->ApplyCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
    if (GetUmLobby()) GetUmLobby()->ApplyCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
  }
  TickUmLobby(R.Showing == TEXT("lobby"));
  if (R.Boot.IsValid() && R.Showing == TEXT("boot")) {
    R.Boot->ApplyModel(R.Model, Now);
    // SC-05 keys: Enter = return, Esc = lobby (the viewport keeps the keyboard on this screen)
    APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    if (PC && R.Model.bResume) {
      if (PC->WasInputKeyJustPressed(EKeys::Enter)) R.Boot->HandleKey(EKeys::Enter);
      if (PC->WasInputKeyJustPressed(EKeys::Escape)) R.Boot->HandleKey(EKeys::Escape);
    }
  }

  // ---- evidence: one frame per sub-state (-S08ScreenShots + -S09ShotDir)
  if (R.Shots < 0) R.Shots = FParse::Param(FCommandLine::Get(), TEXT("S08ScreenShots")) && !S09ShotDir.IsEmpty() ? 1 : 0;
  if (R.Shots == 1 && !R.bBgHidden) {
    FString Sub;
    if (R.Showing == TEXT("boot") && R.Boot.IsValid() && R.Boot->GetAlpha() >= 1.0f) {
      const FUmBootModel& M = R.Model;
      const UUmBootResume* RM = R.Boot->GetResume();
      if (M.bResume) {
        // resuming: once its spinner shows (300 ms, HB-47); resume: the modal fully in
        Sub = M.bResuming ? (RM && RM->ResumeSpinner && RM->ResumeSpinner->IsShown() ? TEXT("resuming") : TEXT(""))
                          : (RM && RM->GetAlpha() >= 1.0f ? TEXT("resume") : TEXT(""));
      } else if (M.bError) {
        Sub = M.bRetrying ? TEXT("retrying") : TEXT("error");
      } else if (M.Stage == EUmBootStage::Session) {
        if (R.BootShownAtMs >= 0.0 && Now - R.BootShownAtMs >= BootMs - 600.0) Sub = TEXT("loading-session");
      } else if (M.Stage == EUmBootStage::Heroes) {
        Sub = M.bHeroesLoaded ? TEXT("loading-heroes") : TEXT("loading-heroes-wait");
      } else if (M.Stage == EUmBootStage::Boards) {
        Sub = TEXT("loading-boards");
      }
      if (!Sub.IsEmpty()) Sub = TEXT("UI-SCR-BOOT-") + Sub;
    } else if (R.Showing == TEXT("login") && R.Login.IsValid() && R.Login->GetAlpha() >= 1.0f) {
      const UUmScreenLogin& L = *R.Login;
      const EUmLoginError E = L.GetError();
      Sub = TEXT("UI-SCR-LOGIN-") + FString(L.IsBusy() ? (L.IsSpinnerShown() ? TEXT("busy") : TEXT("-"))
                                            : E == EUmLoginError::Credentials ? TEXT("error-credentials")
                                            : E == EUmLoginError::Server      ? TEXT("error-server")
                                            : L.HasEmail() && L.HasPassword() ? TEXT("input")
                                                                              : TEXT("empty"));
    }
    if (Sub.EndsWith(TEXT("-"))) Sub.Reset();  // busy before its spinner shows
    if (!Sub.IsEmpty() && !R.ShotKeys.Contains(Sub)) {
      R.ShotKeys.Add(Sub);
      FS08Trace::Write(FString::Printf(TEXT("SCREENSHOT sub=%s file=%s.png"), *Sub, *Sub));
      TakeEvidenceShot(S09ShotDir / (Sub + TEXT(".png")));
    }
  }

  // ---- the evidence drive (review tooling; the credentials come from the process environment only)
  if (R.Drive.IsEmpty() || bAuto) return;
  UUmScreenLogin* L = R.Login.Get();
  UUmScreenBoot* B = R.Boot.Get();
  const bool bLoginReady = L && R.Showing == TEXT("login") && L->GetAlpha() >= 1.0f;
  auto Wait = [&R, Now](double Ms) {
    if (R.DriveAtMs < 0.0) R.DriveAtMs = Now;
    if (Now - R.DriveAtMs < Ms) return false;
    R.DriveAtMs = -1.0;
    return true;
  };
  const FString Email = FPlatformMisc::GetEnvironmentVariable(TEXT("S08_EMAIL"));
  switch (R.DriveStep) {
    case 0:  // LOGIN empty
      if (!bLoginReady || !Wait(1500.0)) return;
      R.DriveStep = UmFsHas(R.Drive, TEXT("bg")) ? 1 : 3;
      FS08Trace::Write(TEXT("MENU-DRIVE step=empty-held"));
      return;
    case 1:  // the menu backdrop without UI (SC-02 menu-bg): hide the route screen for the frame
      if (L) L->SetVisibility(ESlateVisibility::Hidden);
      R.bBgHidden = true;
      if (!S09ShotDir.IsEmpty()) TakeEvidenceShot(S09ShotDir / TEXT("menu-bg.png"));
      FS08Trace::Write(TEXT("MENU-DRIVE step=menu-bg"));
      R.DriveStep = 2;
      return;
    case 2:
      if (!Wait(800.0)) return;
      if (L) L->SetVisibility(ESlateVisibility::Visible);
      R.bBgHidden = false;
      R.DriveStep = 3;
      return;
    case 3:  // input: the email, then both
      if (!bLoginReady || !Wait(500.0)) return;
      L->SetFieldsForTest(Email, FString());
      R.DriveStep = 4;
      return;
    case 4:
      if (!Wait(500.0)) return;
      if (UmFsHas(R.Drive, TEXT("badpass"))) {
        // a wrong password of the same account: the real one + a suffix (never traced)
        L->SetFieldsForTest(Email, FPlatformMisc::GetEnvironmentVariable(TEXT("S08_PASSWORD")) + TEXT("-x"));
      } else {
        L->SetFieldsForTest(Email, FPlatformMisc::GetEnvironmentVariable(TEXT("S08_PASSWORD")));
      }
      L->HandleKey(EKeys::Tab, false, false);  // Email -> Пароль -> «Войти»: the keyboard ring on the primary (04 §3.4)
      L->HandleKey(EKeys::Tab, false, false);
      R.DriveStep = 5;
      return;
    case 5:  // input held, then Enter (one submit)
      if (!Wait(1200.0)) return;
      L->HandleKey(EKeys::Enter, false, false);
      L->HandleKey(EKeys::Enter, false, false);  // a second Enter while busy is refused (SC-06 «Enter — одна отправка»)
      FS08Trace::Write(FString::Printf(TEXT("MENU-DRIVE step=submit submits=%d"), L->GetSubmitCount()));
      R.DriveStep = 6;
      return;
    case 6:  // the answer: an error (held) or the login
      if (!L) return;
      if (!L->IsBusy() && L->GetError() != EUmLoginError::None) {
        if (!Wait(1800.0)) return;
        if (L->GetError() == EUmLoginError::Server || UmFsHas(R.Drive, TEXT("server"))) {
          R.DriveStep = 20;  // error.server: done
          return;
        }
        L->SetFieldsForTest(Email, FPlatformMisc::GetEnvironmentVariable(TEXT("S08_PASSWORD")));
        R.DriveStep = 7;
        return;
      }
      if (Stage == ES08Stage::Login) R.DriveStep = 10;
      return;
    case 7:
      if (!Wait(800.0)) return;
      L->Submit(TEXT("drive"));
      R.DriveStep = 6;
      return;
    case 10:  // the BOOT pass: the error banner (held, then Retry), the resume modal (held, then the plan's answer)
      if (!B) return;
      if (R.Model.bError && !R.Model.bRetrying) {
        if (!Wait(1800.0)) return;
        if (UmFsHas(R.Drive, TEXT("retry"))) B->SimulatePress(FName(TEXT("screens.boot.retry")));
        return;
      }
      if (R.Model.bResume && !R.Model.bResuming && B->IsResumeShown() && B->GetResume()->GetAlpha() >= 1.0f) {
        if (!Wait(2500.0)) return;
        B->SimulatePress(FName(UmFsHas(R.Drive, TEXT("lobby")) ? TEXT("screens.boot.lobby") : TEXT("screens.boot.resume")));
        R.DriveStep = 11;
        return;
      }
      if (R.bPassDone || Stage == ES08Stage::Started) R.DriveStep = 11;
      return;
    case 11:  // the end: lobby (the pass done) or the resumed match (its board on screen)
      if (!Wait(Stage == ES08Stage::Started ? 12000.0 : 2500.0)) return;
      R.DriveStep = 20;
      return;
    case 20:
      FS08Trace::Write(TEXT("MENU-DRIVE done"));
      if (UmFsHas(R.Drive, TEXT("exit"))) AutoExitAfter = Elapsed + 1.0f;
      R.DriveStep = 21;
      return;
    default:
      return;
  }
}

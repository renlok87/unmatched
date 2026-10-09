// VS-7 S5 (docs/game-design/visual/05-production-plan.md §3 VS-7, H14; screens.csv SC-31...SC-38; 04-hud-spec.md §1.9-§1.11):
// the game-mode side of RECONNECT (UI/UmReconnectOverlay.h), GAMEOVER (UI/UmScreenGameOver.h) and ABORTED
// (UI/UmScreenAborted.h). Built in the first frame the UMG root exists (the backend flow and the -BenchResult bench).
//
//   reconnect  the root's Reconnect slot (over every modal): the overlay + its own confirm dialog. The inputs are the
//              HB-14 / CUE-017 net watch (NetWatch.bLost - the same edge as the chip's X and the -30 % saturation), the
//              transport ack, the GD-037 recovery and the GD-038 expiry in a match. The desaturation, CUE-017 / CUE-018,
//              the CONN chip and the «Позиции обновлены» toast stay theirs (never triggered here). «Выйти в лобби» ->
//              «Партия останется на сервере.» -> DetachToLobby (no leaveGame: the match goes on, 04 §1.9 «Партия
//              продолжается на сервере»); «Переподключить» -> RetryMatchLoad and a new attempt cycle; «Ко входу» -> LOGIN
//              (the expired session's tokens are already gone; the route holds LOGIN until the press).
//   gameover   follows FS09ResultView (the DE-019 gate, the 500 ms intro, the 250 ms crossfade) with the summary of
//              RebuildResultScreen; the Slate modal and its bar stay collapsed (rollback -S08SlateHud=gameover).
//              «Посмотреть доску» / «К итогам» = ToggleResultBoard, «В лобби» = ReturnToLobbyCommand (the keys stay
//              HandleResultKeys'). SC-37 VS_AI: «Сыграть ещё» -> leaveGame -> createGame(VS_AI, the same board) ->
//              selectHero(the same hero) -> toggleReady -> startGame (UmGameOver::NextAgainStep); the route holds the
//              LOBBY / ROOM screens until the new match starts, then LOADING; a failed step: why.command.rejected.
//   aborted    the room row ABORTED in the live match; «В лобби» / L / Enter = ReturnToLobbyCommand.
//   evidence   review tooling -S08EndDrive=<step+step..>: result (wait for the results at rest), board, results, again,
//              newmatch (wait until «Сыграть ещё» started the new match), manual (wait for the manual state), expired, retry, live
//              (wait until the overlay is gone), aborted (wait for ABORTED), lobby (the shown screen's «В лобби»), inlobby,
//              wait<ms>, shot-<name> (one frame <name>.png in -S09ShotDir), exit. With it the -S09Flow result tail waits.
//   trace      'RECONNECT state=<s> attempt=<n> missed=<n> lost=<ms>' on a change, 'RECONNECT exit ms=200',
//              'RESULT again mode=VS_AI step=<s> ...', 'ABORTED shown who=<named|unknown> turn=<n>', 'HUD-SCREENS end=...'.
#include "S08FlowGameMode.h"

#include "S08ArtLook.h"
#include "S08IconMotion.h"
#include "S08TraceLog.h"
#include "S08UserSettings.h"
#include "UI/UmConfirmDialog.h"
#include "UI/UmHudLayout.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmPortrait.h"
#include "UI/UmReconnectOverlay.h"
#include "UI/UmScreenAborted.h"
#include "UI/UmScreenGameOver.h"
#include "UI/UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/NamedSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

/** Per-run state of the VS-7 S5 screens (owned by the game mode). */
struct FUmEndRuntime {
  bool bBuilt = false;
  bool bTried = false;
  S08ArtLook::FS08SlateHudBlocks Blocks;
  TWeakObjectPtr<UUmReconnectOverlay> Reconnect;
  TWeakObjectPtr<UUmConfirmDialog> ReconnectConfirm;
  TWeakObjectPtr<UUmScreenGameOver> GameOver;
  TWeakObjectPtr<UUmScreenAborted> Aborted;
  FIntPoint LastCanvas = FIntPoint(-1, -1);
  float LastPx = -1.0f;
  bool LastClassS = false;
  // ---- RECONNECT
  bool bWasLost = false;
  double LostSinceMs = -1.0;
  int32 SeqAtLoss = 0;
  double RecoverySinceMs = -1.0;
  ES08Stage LastStage = ES08Stage::Boot;
  bool bExpiredSeen = false;
  bool bExpiredInMatch = false;
  bool bExpiredAck = false;
  bool bDetachSent = false;
  double ExitStartMs = -1.0;
  EUmReconnectState Shown = EUmReconnectState::Hidden;
  FString LastReconnectKey;
  // ---- GAMEOVER
  bool bResultOpenSeen = false;
  bool bKeyChips = true;
  FUmGameOverModel LastModel;
  EUmAgainStep Again = EUmAgainStep::Idle;
  double AgainStepMs = -1.0;
  int32 FlowErrors = 0;
  int32 AgainErrorsAt = 0;
  FString AgainOldGameId;
  FString AgainHeroId;
  FString AgainBoardId;
  // ---- ABORTED
  bool bAbortedShown = false;
  // ---- the gate lines: once per change of a screen's state and fields
  FString ShotKeys[3];
  // ---- evidence: -S08EndDrive=<step+step..> (review tooling)
  FString Drive;
  TArray<FString> Steps;
  int32 Step = 0;
  double StepAtMs = -1.0;
  bool bDriveParsed = false;
};

namespace {
double UmEnNowMs() { return FPlatformTime::Seconds() * 1000.0; }

void UmEnFill(UWidget* W) {
  if (UOverlaySlot* O = W ? Cast<UOverlaySlot>(W->Slot) : nullptr) {
    O->SetHorizontalAlignment(HAlign_Fill);
    O->SetVerticalAlignment(VAlign_Fill);
  }
}
}  // namespace

// ------------------------------------------------------------------------------------------------ build

static void UmEnBuild(AS08FlowGameMode& GM, FUmEndRuntime& R, UUmHudRoot& Root, const TSharedPtr<FS09HudPressArbiter>& Press,
                      TFunction<void(UUmReconnectOverlay*, UUmConfirmDialog*, UUmScreenGameOver*, UUmScreenAborted*)> Wire) {
  UUmReconnectOverlay* Rc = nullptr;
  UUmConfirmDialog* Dlg = nullptr;
  if (!R.Blocks.IsSlate(FName(TEXT("reconnect"))) && Root.Reconnect) {
    // the Reconnect slot holds one child: an overlay with the card and its own confirm (Modals lie under it)
    UOverlay* Host = Root.WidgetTree ? Root.WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("ReconnectHost"))) : nullptr;
    if (Host) {
      Root.Reconnect->SetContent(Host);
      Rc = CreateWidget<UUmReconnectOverlay>(&Root, UUmReconnectOverlay::WidgetClass());
      if (Rc) {
        Host->AddChildToOverlay(Rc);
        UmEnFill(Rc);
      }
      Dlg = CreateWidget<UUmConfirmDialog>(&Root, UUmConfirmDialog::WidgetClass());
      if (Dlg) {
        Host->AddChildToOverlay(Dlg);
        UmEnFill(Dlg);
        Dlg->SetInput(Press);
      }
    }
  }
  UUmScreenGameOver* Go = nullptr;
  UUmScreenAborted* Ab = nullptr;
  if (Root.Modals) {
    if (!R.Blocks.IsSlate(FName(TEXT("gameover")))) {
      Go = CreateWidget<UUmScreenGameOver>(&Root, UUmScreenGameOver::WidgetClass());
      if (Go) {
        Root.Modals->AddChildToOverlay(Go);
        UmEnFill(Go);
      }
    }
    if (!R.Blocks.IsSlate(FName(TEXT("aborted")))) {
      Ab = CreateWidget<UUmScreenAborted>(&Root, UUmScreenAborted::WidgetClass());
      if (Ab) {
        Root.Modals->AddChildToOverlay(Ab);
        UmEnFill(Ab);
      }
    }
  }
  Wire(Rc, Dlg, Go, Ab);
  R.Reconnect = Rc;
  R.ReconnectConfirm = Dlg;
  R.GameOver = Go;
  R.Aborted = Ab;
  FString M1, M2, M3;
  FS08Trace::Write(FString::Printf(TEXT("HUD-SCREENS end reconnect=%s gameover=%s aborted=%s parts=%d%d%d missing=%s"),
                                   Rc ? *Rc->SourceName() : TEXT("slate"), Go ? *Go->SourceName() : TEXT("slate"),
                                   Ab ? *Ab->SourceName() : TEXT("slate"), Rc && Rc->HasAllParts(&M1) ? 1 : 0,
                                   Go && Go->HasAllParts(&M2) ? 1 : 0, Ab && Ab->HasAllParts(&M3) ? 1 : 0,
                                   (M1 + M2 + M3).IsEmpty() ? TEXT("-") : *(M1 + TEXT(" ") + M2 + TEXT(" ") + M3)));
  (void)GM;
}

// ------------------------------------------------------------------------------------------------ queries

bool AS08FlowGameMode::UmGameOverOnUmg() const { return UmEndRt.IsValid() && UmEndRt->GameOver.IsValid(); }

bool AS08FlowGameMode::UmAbortedOnUmg() const { return UmEndRt.IsValid() && UmEndRt->Aborted.IsValid(); }

bool AS08FlowGameMode::UmEndOwnsInput() const {
  if (!UmEndRt.IsValid()) return false;
  const UUmReconnectOverlay* Rc = UmEndRt->Reconnect.Get();
  return Rc && Rc->IsShown();  // RECONNECT: no click reaches the board, Esc is swallowed
}

bool AS08FlowGameMode::UmEndHoldsRoute() const {
  if (!UmEndRt.IsValid()) return false;
  const FUmEndRuntime& R = *UmEndRt;
  const bool bAgain = R.Again != EUmAgainStep::Idle && R.Again != EUmAgainStep::Done && R.Again != EUmAgainStep::Failed;
  return bAgain || (R.bExpiredInMatch && !R.bExpiredAck && R.Reconnect.IsValid());
}

bool AS08FlowGameMode::UmEndDriveOwnsResult() const { return UmEndRt.IsValid() && !UmEndRt->Drive.IsEmpty(); }

// ------------------------------------------------------------------------------------------------ evidence drive

static void UmEnTickDrive(AS08FlowGameMode& GM, FUmEndRuntime& R, double Now, ES08Stage Stage, bool bResultsAtRest, bool bAborted,
                          const FString& ShotDir, TFunction<void(const FString&)> Shot, TFunction<void()> Board) {
  if (R.Step >= R.Steps.Num()) return;
  if (R.StepAtMs < 0.0) R.StepAtMs = Now;
  const FString& S = R.Steps[R.Step];
  const UUmReconnectOverlay* Rc = R.Reconnect.Get();
  UUmScreenGameOver* Go = R.GameOver.Get();
  UUmScreenAborted* Ab = R.Aborted.Get();
  bool bDone = true;
  if (S.StartsWith(TEXT("wait"))) {
    bDone = Now - R.StepAtMs >= FCString::Atod(*S.Mid(4));
  } else if (S == TEXT("result")) {
    bDone = bResultsAtRest;
  } else if (S == TEXT("board") || S == TEXT("results")) {
    const bool bWantBoard = S == TEXT("board");
    if (Go && Go->GetModel().bBoard != bWantBoard) Board();
  } else if (S == TEXT("again")) {
    if (Go) Go->SimulatePress(FName(TEXT("screens.result.again")));
  } else if (S == TEXT("newmatch")) {
    bDone = R.Again == EUmAgainStep::Idle && Stage == ES08Stage::Started && Now - R.StepAtMs > 500.0;
  } else if (S == TEXT("manual")) {
    bDone = Rc && Rc->IsShown() && Rc->GetModel().State == EUmReconnectState::Manual;
  } else if (S == TEXT("expired")) {  // VC Frames: wait for the expired card (the S10 proxy's expiry, ВР-VC-30)
    bDone = Rc && Rc->IsShown() && Rc->GetModel().State == EUmReconnectState::Expired;
  } else if (S == TEXT("retry")) {
    if (UUmReconnectOverlay* W = R.Reconnect.Get()) W->SimulatePress(FName(TEXT("screens.reconnect.retry")));
  } else if (S == TEXT("live")) {
    bDone = !Rc || !Rc->IsShown();
  } else if (S == TEXT("aborted")) {
    bDone = bAborted && Ab && Ab->GetAlpha() >= 1.0f;
  } else if (S == TEXT("lobby")) {
    if (Ab && Ab->IsShown()) {
      Ab->SimulatePress(FName(TEXT("screens.aborted.lobby")));
    } else if (Go && Go->IsShown()) {
      Go->SimulatePress(FName(TEXT("screens.result.lobby")));
    }
  } else if (S == TEXT("inlobby")) {
    bDone = Stage == ES08Stage::Lobby;
  } else if (S.StartsWith(TEXT("shot-"))) {
    if (!ShotDir.IsEmpty()) Shot(ShotDir / (S.Mid(5) + TEXT(".png")));
  } else if (S == TEXT("exit")) {
    FS08Trace::Write(TEXT("ENDDRIVE exit"));
    FPlatformMisc::RequestExit(false);
  }
  if (!bDone) return;
  FS08Trace::Write(FString::Printf(TEXT("ENDDRIVE step=%s n=%d"), *S, R.Step));
  ++R.Step;
  R.StepAtMs = Now;
  (void)GM;
}

// ------------------------------------------------------------------------------------------------ tick

void AS08FlowGameMode::TickUmEndScreens() {
  if (!UmEndRt.IsValid()) UmEndRt = MakeShared<FUmEndRuntime>();
  FUmEndRuntime& R = *UmEndRt;
  if (!R.bTried) {
    if (!UmHudRoot) return;
    R.bTried = true;
    R.Blocks = S08ArtLook::SlateHudBlocks();
    if (!R.Blocks.UmgRoot()) return;
    const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
    const TSharedPtr<FS09HudPressArbiter> Press = HudPress;
    UmEnBuild(*this, R, *UmHudRoot, HudPress, [WeakThis, Press](UUmReconnectOverlay* Rc, UUmConfirmDialog* Dlg, UUmScreenGameOver* Go, UUmScreenAborted* Ab) {
      if (Rc) {
        UUmReconnectOverlay::FInput In;
        In.OnSound = [WeakThis](FName Bank) {
          if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
        };
        const TWeakObjectPtr<UUmConfirmDialog> WeakDlg(Dlg);
        In.OnLeave = [WeakThis, WeakDlg]() {
          AS08FlowGameMode* Self = WeakThis.Get();
          UUmConfirmDialog* Dlg = WeakDlg.Get();
          if (!Self || !Dlg) return;
          UUmConfirmDialog::FRequest Req;
          Req.OwnerUiId = TEXT("UI-SCR-RECONNECT");
          Req.Title = UmText::Get(EUmTable::Screens, TEXT("screens.reconnect.leave"));
          Req.Message = UmText::Get(EUmTable::Screens, TEXT("screens.reconnect.leave.confirm"));
          Req.OnConfirm = [WeakThis]() {
            AS08FlowGameMode* Me = WeakThis.Get();
            if (!Me || !Me->Flow.IsValid() || !Me->UmEndRt.IsValid()) return;
            Me->UmEndRt->bDetachSent = true;
            FS08Trace::Write(TEXT("RECONNECT leave confirmed (detach: the match stays on the server)"));
            Me->Flow->DetachToLobby();
          };
          Req.OnCancel = [WeakThis]() {
            if (AS08FlowGameMode* Me = WeakThis.Get()) Me->PlayScreenSound(FName(TEXT("UI-PANEL-CLOSE")));
            FS08Trace::Write(TEXT("RECONNECT leave cancelled"));
          };
          Dlg->Open(MoveTemp(Req));
          Self->PlayScreenSound(FName(TEXT("UI-PANEL-OPEN")));
          FS08Trace::Write(TEXT("RECONNECT leave asked"));
        };
        In.OnRetry = [WeakThis]() {
          AS08FlowGameMode* Self = WeakThis.Get();
          if (!Self || !Self->Flow.IsValid() || !Self->UmEndRt.IsValid()) return;
          Self->UmEndRt->LostSinceMs = UmEnNowMs();  // a new cycle of five attempts
          FS08Trace::Write(TEXT("RECONNECT retry (manual): a new attempt cycle"));
          Self->Flow->RetryMatchLoad();
        };
        In.OnToLogin = [WeakThis]() {
          AS08FlowGameMode* Self = WeakThis.Get();
          if (!Self || !Self->UmEndRt.IsValid()) return;
          Self->UmEndRt->bExpiredAck = true;  // the route shows LOGIN (the stage is Failed; no old token is reused)
          FS08Trace::Write(TEXT("RECONNECT expired -> LOGIN"));
        };
        Rc->SetInput(Press, MoveTemp(In));
      }
      if (Go) {
        UUmScreenGameOver::FInput In;
        In.OnSound = [WeakThis](FName Bank) {
          if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
        };
        In.OnViewBoard = [WeakThis]() {
          if (AS08FlowGameMode* Self = WeakThis.Get()) Self->ToggleResultBoard(TEXT("button"));
        };
        In.OnLobby = [WeakThis]() {
          AS08FlowGameMode* Self = WeakThis.Get();
          if (!Self) return;
          if (Self->Flow.IsValid() && Self->Flow->GetStage() == ES08Stage::Lobby && Self->UmEndRt.IsValid()) {
            // a «Сыграть ещё» that failed after the leave: the lobby is already there - the screen goes
            Self->UmEndRt->Again = EUmAgainStep::Idle;
            if (UUmScreenGameOver* G = Self->UmEndRt->GameOver.Get()) G->SetViewAlphas(0.0f, 0.0f);
            FS08Trace::Write(TEXT("RESULT again closed -> LOBBY"));
            return;
          }
          Self->ReturnToLobbyCommand();
        };
        In.OnAgain = [WeakThis]() {
          AS08FlowGameMode* Self = WeakThis.Get();
          if (!Self || !Self->Flow.IsValid() || !Self->UmEndRt.IsValid()) return;
          FUmEndRuntime& S = *Self->UmEndRt;
          const FS08RoomState& Room = Self->Flow->GetRoom();
          const bool bInMatch = Self->Flow->GetStage() == ES08Stage::Started && !Room.GameId.IsEmpty();
          if (bInMatch) {  // a retry after a failed chain keeps the first press's board and hero
            S.AgainOldGameId = Room.GameId;
            S.AgainBoardId = Room.BoardId;
            S.AgainHeroId.Reset();
            for (const FS08RoomPlayer& P : Room.Players) {
              if (P.UserId == Self->Flow->GetUserId()) S.AgainHeroId = P.HeroId;
            }
          }
          S.Again = EUmAgainStep::Leave;
          S.AgainStepMs = UmEnNowMs();
          S.AgainErrorsAt = S.FlowErrors;
          FS08Trace::Write(FString::Printf(TEXT("RESULT again mode=VS_AI step=leave board=%s hero=%d sent=%d"), *S.AgainBoardId,
                                           S.AgainHeroId.IsEmpty() ? 0 : 1, bInMatch ? 1 : 0));
          if (bInMatch) {
            Self->bS09LobbyReturnSent = true;  // one leave: Enter / L during the chain send nothing more
            Self->Flow->LeaveRoom();
          }
        };
        Go->SetInput(Press, MoveTemp(In));
      }
      if (Ab) {
        UUmScreenAborted::FInput In;
        In.OnSound = [WeakThis](FName Bank) {
          if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
        };
        In.OnLobby = [WeakThis]() {
          if (AS08FlowGameMode* Self = WeakThis.Get()) Self->ReturnToLobbyCommand();
        };
        Ab->SetInput(Press, MoveTemp(In));
      }
    });
    if (Flow.IsValid()) {
      Flow->OnFlowError.AddLambda([WeakThis](const FS08GraphQLError&) {
        if (AS08FlowGameMode* Self = WeakThis.Get(); Self && Self->UmEndRt.IsValid()) ++Self->UmEndRt->FlowErrors;
      });
    }
    R.bBuilt = true;
  }
  if (!R.bDriveParsed) {
    R.bDriveParsed = true;
    FParse::Value(FCommandLine::Get(), TEXT("S08EndDrive="), R.Drive);
    R.Drive.ParseIntoArray(R.Steps, TEXT("+"), true);
    if (!R.Drive.IsEmpty()) FS08Trace::Write(FString::Printf(TEXT("ENDDRIVE plan=%s"), *R.Drive));
  }
  if (!R.bBuilt) return;
  const double Now = UmEnNowMs();
  const bool bReduced = S08IconMotion::IsReducedMotion();
  // ---- the canvas
  const FUmHudScaleState& Scale = UmHudScale::Current();
  if (Scale.CanvasSu.X > 0 && (Scale.CanvasSu != R.LastCanvas || Scale.PxPerSu() != R.LastPx || Scale.bClassS != R.LastClassS)) {
    R.LastCanvas = Scale.CanvasSu;
    R.LastPx = Scale.PxPerSu();
    R.LastClassS = Scale.bClassS;
    const FVector2D Canvas(Scale.CanvasSu.X, Scale.CanvasSu.Y);
    if (UUmReconnectOverlay* Rc = R.Reconnect.Get()) Rc->ApplyCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
    if (UUmConfirmDialog* Dlg = R.ReconnectConfirm.Get()) Dlg->SetCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
    if (UUmScreenGameOver* Go = R.GameOver.Get()) Go->ApplyCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
    if (UUmScreenAborted* Ab = R.Aborted.Get()) Ab->ApplyCanvas(Canvas, Scale.bClassS, Scale.PxPerSu());
  }
  const ES08Stage Stage = Flow.IsValid() ? Flow->GetStage() : ES08Stage::Started;

  // ---- RECONNECT (SC-31...SC-33)
  if (UUmReconnectOverlay* Rc = R.Reconnect.Get(); Rc && Flow.IsValid() && !bBench) {
    const bool bStarted = Stage == ES08Stage::Started;
    if (Flow->IsSessionExpired() && !R.bExpiredSeen) {
      R.bExpiredSeen = true;
      R.bExpiredInMatch = R.LastStage == ES08Stage::Started || R.bWasLost;
      R.bExpiredAck = false;
    } else if (!Flow->IsSessionExpired()) {
      R.bExpiredSeen = R.bExpiredInMatch = false;
    }
    const bool bLost = bStarted && NetWatch.bLost;
    if (bLost && !R.bWasLost) {
      R.LostSinceMs = Now;
      R.SeqAtLoss = Hud.SequenceNumber;
    }
    const bool bRecovering = bStarted && Flow->IsAwaitingStateRecovery();
    if (bRecovering && R.RecoverySinceMs < 0.0) R.RecoverySinceMs = Now;
    if (!bRecovering) R.RecoverySinceMs = -1.0;
    FUmReconnectInput In;
    // 04 §1.9: a finished (GAMEOVER) or interrupted (ABORTED) match is not a reconnect - its own screen says it
    In.bStarted = bStarted && !R.bDetachSent && !Hud.bGameOver && !Flow->IsRoomAborted();
    In.bLost = bLost;
    In.bAcked = Flow->IsStreamAcked();
    In.bAwaitingRecovery = bRecovering;
    In.bExpiredInMatch = R.bExpiredInMatch && !R.bExpiredAck;
    In.LostForMs = R.LostSinceMs >= 0.0 ? Now - R.LostSinceMs : 0.0;
    In.RecoveryForMs = R.RecoverySinceMs >= 0.0 ? Now - R.RecoverySinceMs : 0.0;
    const EUmReconnectState St = UmReconnect::Decide(In);
    if (St != EUmReconnectState::Hidden) {
      FUmReconnectModel M;
      M.State = St;
      M.Attempt = UmReconnect::AttemptAt(In.LostForMs);
      M.MaxAttempts = UmReconnect::MaxAttempts;
      M.Missed = FMath::Max(0, Hud.SequenceNumber - R.SeqAtLoss);
      M.bLeaveBusy = R.bDetachSent;
      Rc->ApplyModel(M);
      if (R.Shown == EUmReconnectState::Hidden || R.ExitStartMs >= 0.0) Rc->PlayShow();
      R.ExitStartMs = -1.0;
      const FString Key = FString::Printf(TEXT("%s|%d|%d"), UmReconnect::StateName(St), M.Attempt, M.Missed);
      if (Key != R.LastReconnectKey) {
        R.LastReconnectKey = Key;
        FS08Trace::Write(FString::Printf(TEXT("RECONNECT state=%s attempt=%d missed=%d lost=%.0f"), UmReconnect::StateName(St), M.Attempt,
                                         M.Missed, In.LostForMs));
      }
    } else if (R.Shown != EUmReconnectState::Hidden && R.ExitStartMs < 0.0) {
      // SC-33 exit: the card fades in 200 ms (the saturation returns by CUE-018 itself, the toast is HB-40's)
      R.ExitStartMs = Now;
      FS08Trace::Write(FString::Printf(TEXT("RECONNECT exit ms=%.0f from=%s missed=%d"), bReduced ? 100.0 : UmReconnect::ExitMs,
                                       UmReconnect::StateName(R.Shown), FMath::Max(0, Hud.SequenceNumber - R.SeqAtLoss)));
      R.LastReconnectKey.Reset();
      if (UUmConfirmDialog* Dlg = R.ReconnectConfirm.Get(); Dlg && Dlg->IsOpen()) Dlg->Answer(false);
    }
    if (St == EUmReconnectState::Hidden && R.ExitStartMs >= 0.0) {
      const float A = UmReconnect::ExitAlpha(Now - R.ExitStartMs, bReduced);
      Rc->SetAlphaDirect(A);
      if (A <= 0.0f) R.ExitStartMs = -1.0;
    }
    if (!bLost) R.LostSinceMs = -1.0;
    R.bWasLost = bLost;
    R.Shown = St;
    if (Stage != ES08Stage::Started) R.bDetachSent = false;
    R.LastStage = Stage;
  }

  // ---- GAMEOVER (SC-34...SC-37)
  if (UUmScreenGameOver* Go = R.GameOver.Get()) {
    const bool bOpen = ResultView.IsOpen() && IsResultScreenShown();
    const bool bAgainRuns = R.Again != EUmAgainStep::Idle && R.Again != EUmAgainStep::Done && R.Again != EUmAgainStep::Failed;
    if (bOpen) {
      if (!R.bResultOpenSeen) {
        R.bResultOpenSeen = true;
        // ВР-VS7: the chips of the Auto mode are decided by the matches completed BEFORE this one (the open counts it)
        const US08UserSettings* Settings = US08UserSettings::Get();
        const int32 Done = Settings ? Settings->CompletedMatches : 0;
        R.bKeyChips = US08UserSettings::KeyHintsShown(US08UserSettings::KeyHintsModeNow(), FMath::Max(0, Done - (bBench ? 0 : 1)));
      }
      const FString Viewer = ViewerIdNow();
      const FS08RoomState* Room = Flow.IsValid() && !bBench ? &Flow->GetRoom() : nullptr;
      FUmGameOverModel M;
      M.Outcome = Hud.bDraw ? EUmGameOverOutcome::Draw
                  : (Hud.bOutcomeUnknown || !Hud.bWinnerKnown) ? EUmGameOverOutcome::Unknown
                  : Hud.bViewerWon ? EUmGameOverOutcome::Victory
                                   : EUmGameOverOutcome::Defeat;
      const bool bDecided = M.Outcome == EUmGameOverOutcome::Victory || M.Outcome == EUmGameOverOutcome::Defeat;
      M.WinnerHero = bDecided ? ResultSummary.Left.HeroName : FString();
      M.LoserHero = bDecided && ResultSummary.Reason == ES09ResultReason::HeroHpZero ? ResultSummary.Right.HeroName : FString();
      M.Turn = ResultSummary.TurnCount;
      M.DurationSec = ResultSummary.DurationSec;
      M.bVsAi = Room && Room->Mode == TEXT("VS_AI");
      auto Side = [&](const FS09ResultSide& S) {
        FUmGameOverSide O;
        O.HeroName = S.HeroName;
        O.HeroKey = S.HeroName.IsEmpty() ? NAME_None : FName(*UmPortrait::SlugOf(S.HeroName));
        if (S.PlayerId == Viewer) {
          O.Role = UmText::Get(EUmTable::Screens, TEXT("screens.result.you")).ToString();
        } else {
          O.Role = UmText::Get(EUmTable::Screens, TEXT("screens.result.opponent")).ToString();
          if (M.bVsAi) {  // ВР-VS5-SC37-01: in VS_AI the opponent's role word is the bot's nickname from data
            for (const FS08RoomPlayer& P : Room->Players) {
              if (P.UserId == S.PlayerId && !P.Username.IsEmpty()) O.Role = P.Username;
            }
          }
        }
        if (M.Outcome != EUmGameOverOutcome::Draw && S.bHpKnown) {
          O.Hp = S.Hp;
          O.MaxHp = S.MaxHp;
        }
        O.bWinner = bDecided && S.bWinner;
        O.bFallen = (bDecided && !S.bWinner) || M.Outcome == EUmGameOverOutcome::Draw;
        return O;
      };
      M.Left = Side(ResultSummary.Left);
      M.Right = Side(ResultSummary.Right);
      M.bKeyChips = R.bKeyChips;
      M.bBoard = ResultView.IsBoardView();
      M.bLobbyBusy = bS09LobbyReturnSent && R.Again == EUmAgainStep::Idle;
      M.bAgainBusy = bAgainRuns;
      if (const FUmHudLayout* L = UmHudLayoutNow(); L && L->bHasField) {
        Go->SetFieldSu(&L->FieldSu);
      } else {
        Go->SetFieldSu(nullptr);
      }
      const bool bBoardBefore = R.LastModel.bBoard;
      Go->ApplyModel(M);
      R.LastModel = M;
      const int64 T = NowMs();
      Go->SetViewAlphas(ResultView.ResultsAlpha(T), ResultView.BoardBarAlpha(T));
      if (M.bBoard && !bBoardBefore) {
        // SC-36: the strip x FIELD in the HUD-LAYOUT shape of the gate (04 §1.6; class, canvas, field px, overlapField px²)
        const FUmHudLayout* L = UmHudLayoutNow();
        const float Px = Scale.PxPerSu();
        const FString Field = L && L->bHasField ? FString::Printf(TEXT("(%.0f,%.0f,%.0f,%.0f)"), L->FieldSu.Min.X * Px, L->FieldSu.Min.Y * Px,
                                                                  L->FieldSu.GetSize().X * Px, L->FieldSu.GetSize().Y * Px)
                                                : FString(TEXT("none"));
        const FBox2D SR = Go->StripRectSu();
        FS08Trace::Write(FString::Printf(TEXT("HUD-LAYOUT class=%s canvas=%.0fx%.0f scale=%.3f field=%s overlapField=%.0f block=gameover.strip rect=(%.0f,%.0f,%.0f,%.0f)"),
                                         Scale.bClassS ? TEXT("S") : TEXT("L"), Scale.CanvasSu.X * 1.0, Scale.CanvasSu.Y * 1.0, Px, *Field,
                                         Go->StripOverlapFieldPx2(), SR.Min.X * Px, SR.Min.Y * Px, SR.GetSize().X * Px, SR.GetSize().Y * Px));
      }
    } else if (bAgainRuns) {
      // the old match is gone (leaveGame): the screen stays with «Создаём партию…» until the new match starts
      FUmGameOverModel M = R.LastModel;
      M.bAgainBusy = true;
      M.bBoard = false;
      Go->ApplyModel(M);
      Go->SetViewAlphas(1.0f, 0.0f);
    } else if (Go->IsShown()) {
      Go->SetViewAlphas(0.0f, 0.0f);
    }
    if (!bOpen && !bAgainRuns) R.bResultOpenSeen = false;
    // SC-37: the chain
    if (bAgainRuns && Flow.IsValid()) {
      const FS08RoomState& Room = Flow->GetRoom();
      FUmAgainInput In;
      In.bStarted = Stage == ES08Stage::Started;
      In.bLobby = Stage == ES08Stage::Lobby;
      In.bRoom = Stage == ES08Stage::Room && !Room.GameId.IsEmpty() && Room.GameId != R.AgainOldGameId;
      for (const FS08RoomPlayer& P : Room.Players) {
        if (P.UserId != Flow->GetUserId()) continue;
        In.bHeroPicked = !R.AgainHeroId.IsEmpty() && P.HeroId == R.AgainHeroId;
        In.bReady = P.bIsReady;
      }
      In.bNewMatch = In.bStarted && !Room.GameId.IsEmpty() && Room.GameId != R.AgainOldGameId;
      In.bError = R.FlowErrors > R.AgainErrorsAt;
      In.bTimedOut = Now - R.AgainStepMs > UmGameOver::StepTimeoutMs;
      const EUmAgainStep Next = UmGameOver::NextAgainStep(R.Again, In);
      if (Next != R.Again) {
        R.Again = Next;
        R.AgainStepMs = Now;
        R.AgainErrorsAt = R.FlowErrors;
        FS08Trace::Write(FString::Printf(TEXT("RESULT again mode=VS_AI step=%s game=%s"), UmGameOver::AgainStepName(Next),
                                         Next == EUmAgainStep::Done ? *Room.GameId : TEXT("-")));
        switch (Next) {
          case EUmAgainStep::Create: Flow->CreateRoom(TEXT("VS_AI"), R.AgainBoardId); break;
          case EUmAgainStep::Select: Flow->SelectHero(R.AgainHeroId); break;
          case EUmAgainStep::Ready: Flow->ToggleReady(); break;
          case EUmAgainStep::Start: Flow->StartGame(); break;
          case EUmAgainStep::Done: Go->SetViewAlphas(0.0f, 0.0f); break;
          case EUmAgainStep::Failed: {
            UmHudToastReason(FS09Reason::Make(TEXT("why.command.rejected")), 4.0f);
            FUmGameOverModel M = R.LastModel;
            M.bAgainBusy = false;
            Go->ApplyModel(M);
            break;
          }
          default: break;
        }
      }
    }
    // a failed chain after the leave: the screen stays until the player goes to the lobby
    if (R.Again == EUmAgainStep::Failed && !bOpen) {
      if (Stage == ES08Stage::Lobby && Go->IsShown()) {
        FUmGameOverModel M = R.LastModel;
        M.bAgainBusy = false;
        Go->ApplyModel(M);
        Go->SetViewAlphas(1.0f, 0.0f);
      }
    }
    if (R.Again == EUmAgainStep::Done || (R.Again == EUmAgainStep::Failed && Stage == ES08Stage::Started && !bOpen)) R.Again = EUmAgainStep::Idle;
  }

  // ---- ABORTED (SC-38)
  if (UUmScreenAborted* Ab = R.Aborted.Get()) {
    const bool bAborted = Flow.IsValid() && Stage == ES08Stage::Started && Flow->IsRoomAborted();
    if (bAborted) {
      FUmAbortedModel M;
      M.Turn = Hud.bValid ? Hud.TurnCount : 0;
      M.bKeyChips = US08UserSettings::KeyHintsNow();
      M.bLobbyBusy = bS09LobbyReturnSent;
      Ab->ApplyModel(M);  // ВР-SC13: the server names no leaver - «Соперник покинул партию»
      if (!R.bAbortedShown) {
        R.bAbortedShown = true;
        Ab->PlayShow();
        FS08Trace::Write(FString::Printf(TEXT("ABORTED shown who=%s turn=%d"), M.Leaver.IsEmpty() ? TEXT("unknown") : TEXT("named"), M.Turn));
      }
    } else if (R.bAbortedShown) {
      R.bAbortedShown = false;
      Ab->PlayHide();
    }
  }
  // ---- the gate lines 'SHOT widget id=UI-SCR-RECONNECT|GAMEOVER|ABORTED ...' (04 §4.5): once per state change, at rest
  {
    const UUmScreenBase* Screens[3] = {R.Reconnect.Get(), R.GameOver.Get(), R.Aborted.Get()};
    for (int32 I = 0; I < 3; ++I) {
      const UUmScreenBase* Sc = Screens[I];
      if (!Sc || !Sc->IsShown() || Sc->GetAlpha() < 1.0f) {
        if (Sc && !Sc->IsShown()) R.ShotKeys[I].Reset();
        continue;
      }
      const FString Key = Sc->GetScreenState().ToString() + Sc->ShotExtra();
      if (Key == R.ShotKeys[I]) continue;
      R.ShotKeys[I] = Key;
      TArray<FString> Lines;
      Sc->CollectShotLines(Lines);
      if (I == 0) {
        if (const UUmConfirmDialog* Dlg = R.ReconnectConfirm.Get(); Dlg && Dlg->IsOpen()) Dlg->CollectShotLines(Lines);
      }
      for (const FString& Line : Lines) FS08Trace::Write(Line);
    }
  }
  if (R.Steps.Num() > 0) {
    const UUmScreenGameOver* G = R.GameOver.Get();
    const bool bAtRest = G && G->IsShown() && ResultView.IsOpen() && !ResultView.IsBoardView() && ResultView.ResultsAlpha(NowMs()) >= 1.0f;
    const bool bAbortedNow = Flow.IsValid() && Stage == ES08Stage::Started && Flow->IsRoomAborted();
    const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
    UmEnTickDrive(*this, R, Now, Stage, bAtRest, bAbortedNow, S09ShotDir,
                  [WeakThis](const FString& Path) {
                    if (AS08FlowGameMode* Self = WeakThis.Get()) {
                      FS08Trace::Write(FString::Printf(TEXT("ENDDRIVE shot file=%s"), *FPaths::GetCleanFilename(Path)));
                      Self->TakeEvidenceShot(Path);
                    }
                  },
                  [WeakThis]() {
                    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->ToggleResultBoard(TEXT("drive"));
                  });
  }
}

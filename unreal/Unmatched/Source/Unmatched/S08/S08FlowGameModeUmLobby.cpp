// VS-7 S2 (docs/game-design/visual/05-production-plan.md §3 VS-7; screens.csv SC-08...SC-13; 04-hud-spec.md §1.3): the
// game-mode side of the LOBBY screen (UI/UmScreenLobby.h).
//
//   route     LOBBY shows once the player is logged in and the BOOT pass is done (stage Login) or is back in the lobby
//             (stage Lobby) - never in -S08Auto runs (their drive goes on as before) and never with -S08SlateHud=lobby
//             (the GD-036 / GD-029 Slate panels). Create / join leave it through the stage Room (the ROOM screen).
//   data      availableGames(mode ONE_V_ONE) on entry, every 15 s, on «Обновить» / «Повторить», when the window gets
//             its focus back (ВР-H20); 10 s without an answer or a failed one = the error state (SC-13). Rows: the room
//             code, «1×1», the Board row's name (boardList of the BOOT pass; the AGENTS.md names of the two maps until
//             it answers), «n/2», the discs of the players' heroes (heroList names -> the portrait slugs). The player's
//             own room is not listed (joinGame refuses the host). myGames IN_PROGRESS (the BOOT check) -> «Вернуться в
//             мою партию» (ResumeActiveGame - the same return as SC-05).
//   create    FS08FlowController::CreateRoom(ONE_V_ONE | VS_AI, boardId of the chosen tile) - one key per intent (a
//             second press while busy sends nothing); trace 'LOBBY create mode=<mode> board=<id>'.
//   errors    the OnFlowError of the request this screen sent: a code -> «Игра не найдена» / «Комната заполнена»
//             (the code stays), a row -> why.room.full / why.room.started on the row, a create -> «Сервер недоступен»;
//             an answer that never comes ends busy after 12 s.
//   evidence  review tooling: -S08LobbyDrive=<step+step..> drives the screen after the list answered - hold, ai, 1v1,
//             rows (wait for a listed room), sarpedon, marmoreal, code4, code6, badcode (env S08_LOBBY_BADCODE), join,
//             row, create, refresh,
//             wait<N>, exit; the code of code4 / code6 is the first listed room's (or env S08_LOBBY_CODE) - never traced.
//             With -S08ScreenShots and -S09ShotDir one frame per sub-state UI-SCR-LOBBY-<loading|list|empty|error|
//             create-marmoreal|create-sarpedon|create-ai|busy|code-partial|code-full|code-error-notfound|code-error-full>.png.
#include "S08FlowGameMode.h"

#include "S08ArtLook.h"
#include "S08TraceLog.h"
#include "UI/UmBoardChip.h"
#include "UI/UmHudRoot.h"
#include "UI/UmPortrait.h"
#include "UI/UmScreenLobby.h"
#include "UI/UmText.h"
#include "Components/WidgetSwitcher.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

/** Per-run state of the LOBBY screen (owned by the game mode). */
struct FUmLobbyRuntime {
  TWeakObjectPtr<UUmScreenLobby> Screen;
  UmLobby::FUmLobbyPoll Poll;
  int32 SeenAnswers = 0;
  bool bShowing = false;
  bool bListError = false;
  enum class EPending : uint8 { None, Create, Code, Row } Pending = EPending::None;
  FString PendingGameId;
  double PendingSinceMs = -1.0;
  bool bActiveAsked = false;
  // evidence
  int32 Shots = -1;
  TSet<FString> ShotKeys;
  FString CandidateSub;
  double CandidateSinceMs = -1.0;
  FString Drive;
  TArray<FString> Steps;
  int32 Step = 0;
  double StepAtMs = -1.0;
  FString TypedCode;
  FString LastShotKey;
};

namespace {
double UmLbNowMs() { return FPlatformTime::Seconds() * 1000.0; }

const TCHAR* UmLbModeArg(EUmLobbyMode M) { return M == EUmLobbyMode::VsAi ? TEXT("VS_AI") : TEXT("ONE_V_ONE"); }

FString UmLbBoardName(const TMap<FString, FString>& Names, const FString& Id) {
  if (const FString* N = Names.Find(Id)) return *N;
  if (Id == UmLobby::MarmorealId) return UmLobby::MarmorealName;
  if (Id == UmLobby::SarpedonId) return UmLobby::SarpedonName;
  return Id;  // never an invented name: the id as the server gave it
}
}  // namespace

// ------------------------------------------------------------------------------------------------ build

void AS08FlowGameMode::BuildUmLobby() {
  if (!UmLobby.IsValid()) UmLobby = MakeShared<FUmLobbyRuntime>();
  FUmLobbyRuntime& R = *UmLobby;
  FParse::Value(FCommandLine::Get(), TEXT("S08LobbyDrive="), R.Drive);
  R.Drive.ParseIntoArray(R.Steps, TEXT("+"), true);
  if (S08ArtLook::SlateHudBlocks().IsSlate(FName(TEXT("lobby"))) || !UmHudRoot || !UmHudRoot->Screens) {
    FS08Trace::Write(TEXT("HUD-SCREENS lobby=slate reason=-S08SlateHud"));
    return;
  }
  UUmScreenLobby* L = CreateWidget<UUmScreenLobby>(UmHudRoot, UUmScreenLobby::WidgetClass());
  if (!L) return;
  UmHudRoot->Screens->AddChild(L);
  const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  UUmScreenLobby::FInput In;
  In.OnSound = [WeakThis](FName Bank) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
  };
  In.OnRefresh = [WeakThis]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->UmLobby.IsValid()) return;
    Self->UmLobby->Poll.bForce = true;  // an out-of-turn request in this tick; the 15 s poll goes on
    FS08Trace::Write(TEXT("LOBBY refresh"));
  };
  In.OnCreate = [WeakThis](EUmLobbyMode Mode, const FString& BoardId) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->Flow.IsValid() || !Self->UmLobby.IsValid()) return;
    Self->UmLobby->Pending = FUmLobbyRuntime::EPending::Create;
    Self->UmLobby->PendingSinceMs = UmLbNowMs();
    FS08Trace::Write(FString::Printf(TEXT("LOBBY create mode=%s board=%s"), UmLbModeArg(Mode), *BoardId));
    Self->Flow->CreateRoom(UmLbModeArg(Mode), BoardId);
  };
  In.OnJoinRow = [WeakThis](const FString& GameId) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->Flow.IsValid() || !Self->UmLobby.IsValid()) return;
    Self->UmLobby->Pending = FUmLobbyRuntime::EPending::Row;
    Self->UmLobby->PendingGameId = GameId;
    Self->UmLobby->PendingSinceMs = UmLbNowMs();
    FS08Trace::Write(FString::Printf(TEXT("LOBBY join source=row game=%s"), *GameId));
    Self->Flow->JoinRoomById(GameId);
  };
  In.OnJoinCode = [WeakThis](const FString& Code) {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->Flow.IsValid() || !Self->UmLobby.IsValid()) return;
    Self->UmLobby->Pending = FUmLobbyRuntime::EPending::Code;
    Self->UmLobby->PendingSinceMs = UmLbNowMs();
    FS08Trace::Write(TEXT("LOBBY join source=code"));  // never the code itself
    Self->Flow->JoinRoomByCode(Code);
  };
  In.OnRecover = [WeakThis]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->Flow.IsValid()) return;
    FS08Trace::Write(FString::Printf(TEXT("LOBBY recover game=%s"), *Self->Flow->GetActiveGame().GameId));
    if (!Self->Flow->ResumeActiveGame()) FS08Trace::Write(TEXT("LOBBY recover refused"));
  };
  In.OnMenu = []() { FS08Trace::Write(TEXT("LOBBY menu (the PAUSE / settings screen is its own VS-7 step)")); };
  L->SetInput(HudPress, MoveTemp(In));
  R.Screen = L;
  if (Flow.IsValid()) {
    Flow->OnFlowError.AddLambda([WeakThis](const FS08GraphQLError& Error) {
      if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmLobbyFlowError(Error);
    });
  }
  FString Missing;
  FS08Trace::Write(FString::Printf(TEXT("HUD-SCREENS lobby=%s lobbyParts=%d missing=%s drive=%s"), *L->SourceName(),
                                   L->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing,
                                   R.Drive.IsEmpty() ? TEXT("-") : *R.Drive));
}

UUmScreenLobby* AS08FlowGameMode::GetUmLobby() const { return UmLobby.IsValid() ? UmLobby->Screen.Get() : nullptr; }

bool AS08FlowGameMode::UmLobbyWanted(bool bPassDone) const {
  if (bAuto || !GetUmLobby() || !Flow.IsValid()) return false;
  const ES08Stage Stage = Flow->GetStage();
  return (Stage == ES08Stage::Login && bPassDone) || Stage == ES08Stage::Lobby;
}

void AS08FlowGameMode::HandleUmLobbyFlowError(const FS08GraphQLError& Error) {
  if (!UmLobby.IsValid() || !UmLobby->bShowing) return;
  FUmLobbyRuntime& R = *UmLobby;
  UUmScreenLobby* L = R.Screen.Get();
  if (!L || R.Pending == FUmLobbyRuntime::EPending::None) return;  // only the answer of a request this screen sent
  if (R.Pending == FUmLobbyRuntime::EPending::Code) {
    const EUmCodeError E = UmLobby::ClassifyCodeError(Error.Code, Error.Message);
    FS08Trace::Write(FString::Printf(TEXT("LOBBY code error code=%s shown=%s"), *Error.Code, UmLobby::CodeErrorName(E)));
    L->ShowCodeError(E);
  } else if (R.Pending == FUmLobbyRuntime::EPending::Row) {
    const FName Why = UmLobby::RowWhy(Error.Code, Error.Message);
    FS08Trace::Write(FString::Printf(TEXT("LOBBY row unavailable game=%s why=%s code=%s"), *R.PendingGameId, *Why.ToString(), *Error.Code));
    PlayScreenSound(FName(TEXT("UI-REJECT")));
    L->MarkRowUnavailable(R.PendingGameId, Why);
  } else {
    FS08Trace::Write(FString::Printf(TEXT("LOBBY create error code=%s"), *Error.Code));
    L->ShowCreateError();
  }
  R.Pending = FUmLobbyRuntime::EPending::None;
}

// ------------------------------------------------------------------------------------------------ tick

void AS08FlowGameMode::TickUmLobby(bool bShowing) {
  if (!UmLobby.IsValid() || !Flow.IsValid()) return;
  FUmLobbyRuntime& R = *UmLobby;
  UUmScreenLobby* L = R.Screen.Get();
  if (!L) return;
  const double Now = UmLbNowMs();
  if (bShowing != R.bShowing) {
    R.bShowing = bShowing;
    R.Pending = FUmLobbyRuntime::EPending::None;
    if (bShowing) {
      R.Poll.Reset();
      R.bActiveAsked = false;
      R.LastShotKey.Reset();
      if (R.SeenAnswers == 0) L->SetList(EUmLobbyList::Loading, {});
      FS08Trace::Write(TEXT("LOBBY shown"));
      RefreshHud();  // the GD-036 Slate panel steps aside (RefreshHud checks the route)
    } else {
      L->EndBusy();
    }
  }
  if (!bShowing) return;

  // ---- the header and the boards (the BOOT pass loaded them)
  L->SetNickname(Flow->GetUsername());
  const TMap<FString, FString>& Names = Flow->GetBoardNames();
  L->SetBoardNames(UmLbBoardName(Names, UmLobby::MarmorealId), UmLbBoardName(Names, UmLobby::SarpedonId));

  // ---- «Вернуться в мою партию»: the player's live match (myGames IN_PROGRESS, as the BOOT check)
  if (!R.bActiveAsked) {
    R.bActiveAsked = true;
    Flow->FetchActiveGame();
  }
  L->SetRecoverVisible(Flow->GetActiveGameState() == FS08FlowController::EBootQuery::Done && !Flow->GetActiveGame().GameId.IsEmpty());

  // ---- the list (ВР-H20)
  if (R.Poll.Due(Now, FApp::HasFocus())) {
    R.Poll.Sent(Now);
    Flow->FetchAvailableGames();
  }
  if (Flow->GetAvailableAnswers() != R.SeenAnswers) {
    R.SeenAnswers = Flow->GetAvailableAnswers();
    R.Poll.Answered();
    if (Flow->GetAvailableState() == FS08FlowController::EBootQuery::Done) {
      TArray<FUmLobbyRowModel> Rows;
      const FText Mode1v1 = UmText::Get(EUmTable::Screens, TEXT("screens.lobby.create.mode.1v1"));
      for (const FS08FlowController::FLobbyGame& G : Flow->GetAvailableGames()) {
        if (G.HostId == Flow->GetUserId()) continue;  // the player's own room (joinGame refuses the host)
        FUmLobbyRowModel M;
        M.GameId = G.Id;
        M.Code = G.Code;
        M.Mode = G.Mode == TEXT("ONE_V_ONE") ? Mode1v1 : FText::FromString(G.Mode);
        M.Board = UmLbBoardName(Names, G.BoardId);
        M.Seats = FMath::Max(1, G.Players);
        for (const FString& HeroId : G.HeroIds) {
          const FS08HeroEntry* H = Flow->GetHeroes().FindByPredicate([&HeroId](const FS08HeroEntry& E) { return E.Id == HeroId; });
          if (!H) continue;
          M.HeroKeys.Add(FName(*UmPortrait::SlugOf(H->Name)));
          M.HeroNames.Add(H->Name);
        }
        Rows.Add(MoveTemp(M));
      }
      L->SetList(Rows.Num() ? EUmLobbyList::List : EUmLobbyList::Empty, Rows);
      R.bListError = false;
      FS08Trace::Write(FString::Printf(TEXT("LOBBY list state=%s rows=%d"), UmLobby::ListName(L->GetList()), Rows.Num()));
    } else if (!R.bListError) {
      R.bListError = true;
      L->SetList(EUmLobbyList::Error, {});
      PlayScreenSound(FName(TEXT("UI-REJECT")));
      FS08Trace::Write(TEXT("LOBBY list state=error reason=failed"));
    }
  }
  if (R.Poll.TimedOut(Now) && !R.bListError) {
    R.bListError = true;
    L->SetList(EUmLobbyList::Error, {});
    PlayScreenSound(FName(TEXT("UI-REJECT")));
    FS08Trace::Write(FString::Printf(TEXT("LOBBY list state=error reason=timeout waited=%.0f"), Now - R.Poll.InFlightSinceMs));
  }

  // ---- an answer that never came (the flow refused to send, a lost reply): busy ends after 12 s
  if (R.Pending != FUmLobbyRuntime::EPending::None && Now - R.PendingSinceMs > 12000.0 && L->IsBusy()) {
    FS08Trace::Write(TEXT("LOBBY busy timeout"));
    if (R.Pending == FUmLobbyRuntime::EPending::Create) {
      L->ShowCreateError();
    } else {
      L->EndBusy();
    }
    R.Pending = FUmLobbyRuntime::EPending::None;
  }

  // ---- the gate line (04 §4.5 / §7.1): 'SHOT widget id=UI-SCR-LOBBY ...' once per change of the state and its fields
  {
    const FString Key = L->GetScreenState().ToString() + L->ShotExtra();
    if (Key != R.LastShotKey && L->GetAlpha() >= 1.0f) {
      R.LastShotKey = Key;
      TArray<FString> Lines;
      L->CollectShotLines(Lines);
      for (const FString& Line : Lines) FS08Trace::Write(Line);
    }
  }

  // ---- evidence: one frame per sub-state, once it held 300 ms (-S08ScreenShots + -S09ShotDir)
  if (R.Shots < 0) R.Shots = FParse::Param(FCommandLine::Get(), TEXT("S08ScreenShots")) && !S09ShotDir.IsEmpty() ? 1 : 0;
  if (R.Shots == 1 && L->GetAlpha() >= 1.0f) {
    FString Sub;
    const int32 CodeLen = L->GetCode().Len();
    if (L->GetCodeError() != EUmCodeError::None) {
      Sub = L->GetCodeError() == EUmCodeError::Full ? TEXT("code-error-full") : TEXT("code-error-notfound");
    } else if (L->IsCreateBusy()) {
      Sub = L->IsCreateSpinnerShown() ? TEXT("busy") : TEXT("");
    } else if (CodeLen > 0) {
      Sub = CodeLen == UmLobby::CodeLength ? TEXT("code-full") : TEXT("code-partial");
    } else if (L->IsCreateTouched()) {
      Sub = L->GetMode() == EUmLobbyMode::VsAi ? TEXT("create-ai")
                                               : (L->GetBoardId() == UmLobby::SarpedonId ? TEXT("create-sarpedon") : TEXT("create-marmoreal"));
    } else if (L->GetList() != EUmLobbyList::Loading || L->IsSkeletonShown()) {
      Sub = UmLobby::ListName(L->GetList());
    }
    if (Sub != R.CandidateSub) {
      R.CandidateSub = Sub;
      R.CandidateSinceMs = Now;
    }
    if (!Sub.IsEmpty() && Now - R.CandidateSinceMs >= 300.0 && !R.ShotKeys.Contains(Sub)) {
      R.ShotKeys.Add(Sub);
      const FString File = TEXT("UI-SCR-LOBBY-") + Sub;
      FS08Trace::Write(FString::Printf(TEXT("SCREENSHOT sub=%s file=%s.png"), *File, *File));
      TakeEvidenceShot(S09ShotDir / (File + TEXT(".png")));
    }
  }

  // ---- the evidence drive (review tooling): after the list answered, one step at a time
  if (R.Steps.Num() == 0 || bAuto || R.Step >= R.Steps.Num() || L->GetAlpha() < 1.0f) return;
  if (L->GetList() == EUmLobbyList::Loading) return;
  if (R.StepAtMs < 0.0) R.StepAtMs = Now;
  const FString& S = R.Steps[R.Step];
  auto Next = [&R, Now](double HoldMs) {
    if (Now - R.StepAtMs < HoldMs) return false;
    ++R.Step;
    R.StepAtMs = Now;
    return true;
  };
  auto RowCode = [&L]() {
    const FString Env = FPlatformMisc::GetEnvironmentVariable(TEXT("S08_LOBBY_CODE"));
    if (!Env.IsEmpty()) return Env;
    const UUmLobbyGameRow* Row = L->GetRow(0);
    return Row ? Row->GetModel().Code : FString();
  };
  if (S == TEXT("hold")) {
    Next(2500.0);
  } else if (S == TEXT("rows")) {  // wait for a listed room (another client creates it), at most 60 s
    if (L->GetRowCount() > 0 || Now - R.StepAtMs > 60000.0) {
      FS08Trace::Write(FString::Printf(TEXT("LOBBY-DRIVE step=rows n=%d waited=%.0f"), L->GetRowCount(), Now - R.StepAtMs));
      ++R.Step;
      R.StepAtMs = -1.0;
    }
  } else if (S.StartsWith(TEXT("wait"))) {
    Next(1000.0 * FCString::Atoi(*S.RightChop(4)));
  } else if (S == TEXT("ai") || S == TEXT("1v1") || S == TEXT("sarpedon") || S == TEXT("marmoreal") || S == TEXT("refresh") ||
             S == TEXT("row") || S == TEXT("create") || S == TEXT("join")) {
    if (Now - R.StepAtMs < 800.0) return;  // the previous state holds its frame
    const FName Id(S == TEXT("ai") ? TEXT("screens.lobby.create.mode.ai")
                   : S == TEXT("1v1") ? TEXT("screens.lobby.create.mode.1v1")
                   : S == TEXT("sarpedon") ? TEXT("screens.lobby.board.1")
                   : S == TEXT("marmoreal") ? TEXT("screens.lobby.board.0")
                   : S == TEXT("refresh") ? TEXT("common.btn.refresh")
                   : S == TEXT("row") ? TEXT("screens.lobby.row.join.0")
                   : S == TEXT("join") ? TEXT("screens.lobby.code.submit")
                                       : TEXT("screens.lobby.create.submit"));
    L->SimulatePress(Id);
    FS08Trace::Write(FString::Printf(TEXT("LOBBY-DRIVE step=%s"), *S));
    ++R.Step;
    R.StepAtMs = -1.0;
  } else if (S == TEXT("code4") || S == TEXT("code6")) {
    if (Now - R.StepAtMs < 800.0) return;
    const FString Code = RowCode();
    L->SetCodeText(Code.Left(S == TEXT("code4") ? 4 : 6), true);
    FS08Trace::Write(FString::Printf(TEXT("LOBBY-DRIVE step=%s chars=%d"), *S, L->GetCode().Len()));
    ++R.Step;
    R.StepAtMs = -1.0;
  } else if (S == TEXT("badcode")) {
    if (Now - R.StepAtMs < 800.0) return;
    L->SetCodeText(FPlatformMisc::GetEnvironmentVariable(TEXT("S08_LOBBY_BADCODE")), true);
    L->SimulatePress(FName(TEXT("screens.lobby.code.submit")));
    FS08Trace::Write(FString::Printf(TEXT("LOBBY-DRIVE step=badcode chars=%d"), L->GetCode().Len()));
    ++R.Step;
    R.StepAtMs = -1.0;
  } else if (S == TEXT("exit")) {
    FS08Trace::Write(TEXT("LOBBY-DRIVE done"));
    AutoExitAfter = Elapsed + 1.0f;
    ++R.Step;
  } else {
    FS08Trace::Write(FString::Printf(TEXT("LOBBY-DRIVE unknown step=%s"), *S));
    ++R.Step;
  }
}

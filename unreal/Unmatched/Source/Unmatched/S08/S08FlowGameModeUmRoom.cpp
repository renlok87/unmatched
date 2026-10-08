// VS-7 S3 (docs/game-design/visual/05-production-plan.md §3 VS-7; screens.csv SC-14...SC-20; 04-hud-spec.md §1.4, §1.5):
// the game-mode side of the ROOM screen (UI/UmScreenRoom.h) and of the match loading (UI/UmScreenLoading.h).
//
//   route     ROOM shows in the stage Room and, after the start, while the countdown / «Партия начинается…» runs: the
//             host who pressed «Начать партию» sees 3-2-1 (1000 ms each, the answer of startGame put the stage to Started
//             - the countdown never delays the server match) and then «Партия начинается…»; the guest (and any start this
//             screen did not send) sees only «Партия начинается…» for 1000 ms (ВР-VS7-30). LOADING shows from then until
//             the first snapshot's scene is up (the board actor with its figures), also on a resume from BOOT / LOBBY.
//             Never in -S08Auto runs (their drive goes on as before); -S08SlateHud=room | loading keep the old views.
//   data      FS08RoomState (code, mode, host, board, players: hero, ready, seat), heroList names -> the MVP roster cards
//             (King Arthur, Medusa: ВР-02, ВР-H12), adminHero(id) per card / seat hero (HP, move, attack, sidekicks,
//             ability), cardList(heroId) for the deck count and the INSPECT deck mode, boardList names.
//   actions   SelectHero / ToggleReady / StartGame (busy with why.syncing until the room answer, at most 8 s), LeaveRoom
//             through UUmConfirmDialog «Выйти из комнаты?», «Просмотр колоды» -> an own UUmScreenInspect in deck mode from
//             the hero's catalogue (composition only, F-05), «Копировать» -> the clipboard (never traced).
//   sound     UI-SELECT on a pick, PlayHeroSelectSting(<hero>) when the server confirmed it; UI-PANEL-OPEN / -CLOSE with the
//             deck modal and the leave dialog; the host's countdown UI-ROOM-COUNT per digit and UI-ROOM-COUNT-GO at its end;
//             UI-NET-LOST on the loading error. Room joins, ready, start, leave, the room layer and STG-MATCH-START play by
//             themselves (08-screen-audio-hooks) - never called here.
//   loading   stages connect (gameSequence) -> state (gameState: the first applied snapshot) -> board (the board actor and
//             its figures) -> GAME; each stage reads at least 600 ms (ВР-VS7-31); 10 s from the screen without the first
//             snapshot = the error: «Повторить» asks gameSequence + gameState again (the stream reconnects at once),
//             «В лобби» detaches locally - the match stays IN_PROGRESS (the way back: LOBBY «Вернуться в мою партию»).
//   evidence  review tooling: -S08RoomDrive=<step+step..> (hold, wait<N>, opp, opphero, oppready, pick-arthur, pick-medusa,
//             forcepick-arthur, forcepick-medusa, deck, deckclose, ready, start, leave, leaveno, leaveyes, copy, errretry,
//             errlobby, game, exit); with -S08ScreenShots and -S09ShotDir one frame per sub-state
//             UI-SCR-ROOM-<host|guest>-<waiting|picked|ready>[-taken][-ai][-sarpedon], UI-SCR-ROOM-<deck|leave|countdown-3|
//             starting>; the LOADING stages through the base queue UI-SCR-LOADING-<connect|state|board|error>.png.
#include "S08FlowGameMode.h"

#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08TraceLog.h"
#include "UI/UmConfirmDialog.h"
#include "UI/UmHudRoot.h"
#include "UI/UmPortrait.h"
#include "UI/UmScreenInspect.h"
#include "UI/UmScreenLoading.h"
#include "UI/UmScreenLobby.h"
#include "UI/UmScreenRoom.h"
#include "UI/UmText.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/WidgetSwitcher.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformApplicationMisc.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

/** Per-run state of the ROOM and LOADING screens (owned by the game mode). */
struct FUmRoomRuntime {
  TWeakObjectPtr<UUmScreenRoom> Room;
  TWeakObjectPtr<UUmScreenLoading> Loading;
  TWeakObjectPtr<UUmScreenInspect> Inspect;
  TWeakObjectPtr<UUmConfirmDialog> Confirm;
  ES08Stage LastStage = ES08Stage::Boot;
  bool bRoomShown = false;    // the ROOM screen was on in the stage Room (the start then shows its countdown)
  bool bStartPressed = false;
  EUmRoomPhase Phase = EUmRoomPhase::Room;
  double PhaseStartMs = -1.0;
  int32 LastDigit = -1;
  // room actions
  bool bBusy = false;
  double BusySinceMs = -1.0;
  FString BusyKey;
  FString PendingPickHeroId;
  FString LastOwnHeroId;
  FString ForcedTakenHeroId;
  TSet<FString> Asked;
  FString LastBoardTraced;
  FString LastShotKey;
  // loading
  bool bLoadingDone = true;
  bool bLoadingShowing = false;
  double LoadingShownMs = -1.0;
  EUmLoadingStage LStage = EUmLoadingStage::Connect;
  double LStageMs = -1.0;
  int32 AppliedBase = 0;
  int32 BoardReadyFrames = 0;
  FString LastLoadingShotKey;
  // evidence
  int32 Shots = -1;
  TSet<FString> ShotKeys;
  FString CandidateSub;
  double CandidateSinceMs = -1.0;
  FString Drive;
  TArray<FString> Steps;
  int32 Step = 0;
  double StepAtMs = -1.0;
  bool bDriveArmed = false;
  double ErrHeldMs = -1.0;
};

namespace {
double UmRmNowMs() { return FPlatformTime::Seconds() * 1000.0; }

/** The MVP roster (ВР-02): the heroes the ROOM offers, in the card order of the accepted mockup. */
const TCHAR* const UmRmRoster[] = {TEXT("King Arthur"), TEXT("Medusa")};

FString UmRmBoardName(const TMap<FString, FString>& Names, const FString& Id) {
  if (const FString* N = Names.Find(Id)) return *N;
  if (Id == UmLobby::MarmorealId) return UmLobby::MarmorealName;
  if (Id == UmLobby::SarpedonId) return UmLobby::SarpedonName;
  return Id;
}

const FS08HeroEntry* UmRmHero(const TArray<FS08HeroEntry>& Heroes, const FString& Id) {
  return Heroes.FindByPredicate([&Id](const FS08HeroEntry& E) { return E.Id == Id; });
}

FString UmRmRoomKey(const FS08RoomState& R) {
  FString K = R.Status + TEXT("|");
  for (const FS08RoomPlayer& P : R.Players) K += FString::Printf(TEXT("%s:%s:%d;"), *P.UserId, *P.HeroId, P.bIsReady ? 1 : 0);
  return K;
}
}  // namespace

// ------------------------------------------------------------------------------------------------ build

void AS08FlowGameMode::BuildUmRoom() {
  if (!UmRoomRt.IsValid()) UmRoomRt = MakeShared<FUmRoomRuntime>();
  FUmRoomRuntime& R = *UmRoomRt;
  FParse::Value(FCommandLine::Get(), TEXT("S08RoomDrive="), R.Drive);
  R.Drive.ParseIntoArray(R.Steps, TEXT("+"), true);
  if (!UmHudRoot || !UmHudRoot->Screens) return;
  const S08ArtLook::FS08SlateHudBlocks Blocks = S08ArtLook::SlateHudBlocks();
  const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  // ---- ROOM
  if (Blocks.IsSlate(FName(TEXT("room")))) {
    FS08Trace::Write(TEXT("HUD-SCREENS room=slate reason=-S08SlateHud"));
  } else if (UUmScreenRoom* Room = CreateWidget<UUmScreenRoom>(UmHudRoot, UUmScreenRoom::WidgetClass())) {
    UmHudRoot->Screens->AddChild(Room);
    UUmScreenRoom::FInput In;
    In.OnSound = [WeakThis](FName Bank) {
      if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
    };
    auto Busy = [WeakThis]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Self->UmRoomRt.IsValid() || !Self->Flow.IsValid()) return false;
      FUmRoomRuntime& S = *Self->UmRoomRt;
      S.bBusy = true;
      S.BusySinceMs = UmRmNowMs();
      S.BusyKey = UmRmRoomKey(Self->Flow->GetRoom());
      return true;
    };
    In.OnPick = [WeakThis, Busy](const FString& HeroId) {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Busy()) return;
      Self->UmRoomRt->PendingPickHeroId = HeroId;
      FS08Trace::Write(FString::Printf(TEXT("ROOM pick hero=%s"), *HeroId));
      Self->Flow->SelectHero(HeroId);
    };
    In.OnReady = [WeakThis, Busy]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Busy()) return;
      FS08Trace::Write(TEXT("ROOM ready toggle"));
      Self->Flow->ToggleReady();
    };
    In.OnStart = [WeakThis, Busy]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Busy()) return;
      Self->UmRoomRt->bStartPressed = true;
      FS08Trace::Write(TEXT("ROOM start"));
      Self->Flow->StartGame();
    };
    In.OnLeave = [WeakThis]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (Self) Self->OpenUmRoomLeave();
    };
    In.OnDeck = [WeakThis]() {
      if (AS08FlowGameMode* Self = WeakThis.Get()) Self->OpenUmRoomDeck();
    };
    In.OnCopy = [WeakThis]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Self->Flow.IsValid() || Self->Flow->GetRoom().Code.IsEmpty()) return;
      FPlatformApplicationMisc::ClipboardCopy(*Self->Flow->GetRoom().Code);
      FS08Trace::Write(TEXT("ROOM code copied"));  // never the code itself
    };
    In.OnMenu = [WeakThis]() {  // VS-7 S4 SC-24: PAUSE from the header
    if (AS08FlowGameMode* Self = WeakThis.Get(); !Self || !Self->OpenUmPause(TEXT("menu"))) FS08Trace::Write(TEXT("ROOM menu (no PAUSE)"));
  };
    Room->SetInput(HudPress, MoveTemp(In));
    R.Room = Room;
    // the deck modal and the leave dialog of this screen (Modals: over the screens)
    if (UmHudRoot->Modals && !Blocks.IsSlate(FName(TEXT("inspect")))) {
      if (UUmScreenInspect* Insp = CreateWidget<UUmScreenInspect>(UmHudRoot, UUmScreenInspect::WidgetClass())) {
        if (UOverlaySlot* O = UmHudRoot->Modals->AddChildToOverlay(Insp)) {
          O->SetHorizontalAlignment(HAlign_Fill);
          O->SetVerticalAlignment(VAlign_Fill);
        }
        UUmScreenInspect::FInput II;
        II.OnClose = [WeakThis](const TCHAR* Why) {
          if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(FName(TEXT("UI-PANEL-CLOSE")));
          FS08Trace::Write(FString::Printf(TEXT("INSPECT close why=%s source=room"), Why));
        };
        II.OnPage = [](int32 Index) { FS08Trace::Write(FString::Printf(TEXT("INSPECT page index=%d source=room"), Index)); };
        Insp->SetInput(HudPress, MoveTemp(II));
        R.Inspect = Insp;
      }
    }
    if (UmHudRoot->Modals) {
      if (UUmConfirmDialog* Dlg = CreateWidget<UUmConfirmDialog>(UmHudRoot, UUmConfirmDialog::WidgetClass())) {
        if (UOverlaySlot* O = UmHudRoot->Modals->AddChildToOverlay(Dlg)) {
          O->SetHorizontalAlignment(HAlign_Fill);
          O->SetVerticalAlignment(VAlign_Fill);
        }
        Dlg->SetInput(HudPress);
        R.Confirm = Dlg;
      }
    }
    FString Missing;
    FS08Trace::Write(FString::Printf(TEXT("HUD-SCREENS room=%s roomParts=%d missing=%s inspect=%d confirm=%d drive=%s"), *Room->SourceName(),
                                     Room->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing, R.Inspect.IsValid() ? 1 : 0,
                                     R.Confirm.IsValid() ? 1 : 0, R.Drive.IsEmpty() ? TEXT("-") : *R.Drive));
  }
  // ---- LOADING
  if (Blocks.IsSlate(FName(TEXT("loading")))) {
    FS08Trace::Write(TEXT("HUD-SCREENS loading=slate reason=-S08SlateHud"));
  } else if (UUmScreenLoading* L = CreateWidget<UUmScreenLoading>(UmHudRoot, UUmScreenLoading::WidgetClass())) {
    UmHudRoot->Screens->AddChild(L);
    UUmScreenLoading::FInput In;
    In.OnSound = [WeakThis](FName Bank) {
      if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
    };
    In.OnRetry = [WeakThis]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Self->Flow.IsValid() || !Self->UmRoomRt.IsValid()) return;
      FUmRoomRuntime& S = *Self->UmRoomRt;
      const double Now = UmRmNowMs();
      S.LoadingShownMs = Now;  // the next 10 s count from the retry
      S.LStage = EUmLoadingStage::Connect;
      S.LStageMs = Now;
      FS08Trace::Write(TEXT("LOADING retry pressed"));
      Self->Flow->RetryMatchLoad();
    };
    In.OnLobby = [WeakThis]() {
      AS08FlowGameMode* Self = WeakThis.Get();
      if (!Self || !Self->Flow.IsValid() || !Self->UmRoomRt.IsValid()) return;
      Self->UmRoomRt->bLoadingDone = true;
      FS08Trace::Write(TEXT("LOADING lobby pressed (the match stays on the server)"));
      Self->Flow->DetachToLobby();
    };
    L->SetInput(HudPress, MoveTemp(In));
    R.Loading = L;
    FString Missing;
    FS08Trace::Write(FString::Printf(TEXT("HUD-SCREENS loading=%s loadingParts=%d missing=%s"), *L->SourceName(), L->HasAllParts(&Missing) ? 1 : 0,
                                     Missing.IsEmpty() ? TEXT("-") : *Missing));
  }
  if (Flow.IsValid()) {
    Flow->OnFlowError.AddLambda([WeakThis](const FS08GraphQLError& Error) {
      if (AS08FlowGameMode* Self = WeakThis.Get()) Self->HandleUmRoomFlowError(Error);
    });
  }
}

UUmScreenRoom* AS08FlowGameMode::GetUmRoom() const { return UmRoomRt.IsValid() ? UmRoomRt->Room.Get() : nullptr; }
UUmScreenLoading* AS08FlowGameMode::GetUmLoading() const { return UmRoomRt.IsValid() ? UmRoomRt->Loading.Get() : nullptr; }

bool AS08FlowGameMode::UmRoomBusy() const { return UmRoomRt.IsValid() && UmRoomRt->bBusy; }

void AS08FlowGameMode::HandleUmRoomFlowError(const FS08GraphQLError& Error) {
  if (!UmRoomRt.IsValid() || !UmRoomRt->bBusy) return;
  FUmRoomRuntime& R = *UmRoomRt;
  if (!R.PendingPickHeroId.IsEmpty()) {
    // «Герой уже выбран другим игроком этой игры»: the card says why.hero.taken until the next room answer
    R.ForcedTakenHeroId = R.PendingPickHeroId;
    PlayScreenSound(FName(TEXT("UI-REJECT")));
    FS08Trace::Write(FString::Printf(TEXT("ROOM pick refused hero=%s why=why.hero.taken code=%s"), *R.PendingPickHeroId, *Error.Code));
  } else {
    FS08Trace::Write(FString::Printf(TEXT("ROOM action refused code=%s"), *Error.Code));
  }
  R.PendingPickHeroId.Reset();
  R.bBusy = false;
  R.bStartPressed = false;
}

void AS08FlowGameMode::OpenUmRoomLeave() {
  if (!UmRoomRt.IsValid() || !UmRoomRt->Confirm.IsValid()) {
    if (Flow.IsValid()) Flow->LeaveRoom();  // no dialog widget: leave as the old panel did
    return;
  }
  const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  UUmConfirmDialog::FRequest Req;
  Req.OwnerUiId = TEXT("UI-SCR-ROOM");
  Req.Title = UmText::Get(EUmTable::Screens, TEXT("screens.room.leave.confirm"));
  Req.OnConfirm = [WeakThis]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->Flow.IsValid()) return;
    FS08Trace::Write(TEXT("ROOM leave confirmed"));
    Self->Flow->LeaveRoom();
  };
  Req.OnCancel = [WeakThis]() {
    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(FName(TEXT("UI-PANEL-CLOSE")));
    FS08Trace::Write(TEXT("ROOM leave cancelled"));
  };
  UmRoomRt->Confirm->Open(MoveTemp(Req));
  PlayScreenSound(FName(TEXT("UI-PANEL-OPEN")));
  FS08Trace::Write(TEXT("ROOM leave asked"));
}

void AS08FlowGameMode::OpenUmRoomDeck() {
  if (!UmRoomRt.IsValid() || !Flow.IsValid()) return;
  FUmRoomRuntime& R = *UmRoomRt;
  UUmScreenInspect* S = R.Inspect.Get();
  const FS08RoomPlayer* Me = Flow->GetRoom().Players.FindByPredicate([this](const FS08RoomPlayer& P) { return P.UserId == Flow->GetUserId(); });
  const TArray<FS08FlowController::FHeroDeckCard>* Deck = Me ? Flow->FindHeroDeck(Me->HeroId) : nullptr;
  if (!S || !Me || !Deck) {
    FS08Trace::Write(TEXT("INSPECT deck refused source=room why=no-list"));
    return;
  }
  // the hero's catalogue as a deck list (no instance id, no order: F-05)
  FS09DeckList List;
  List.PlayerId = Me->UserId;
  for (const FS08FlowController::FHeroDeckCard& C : *Deck) {
    FS09DeckListCard D;
    D.CardId = C.CardId;
    D.Name = C.Name;
    D.NameRu = C.NameRu;
    D.CardType = C.CardType;
    D.BannerName = C.BannerName;
    D.AttackValue = C.Attack;
    D.DefenseValue = C.Defense;
    D.BoostValue = C.Boost;
    D.Count = C.Count;
    List.Total += C.Count;
    List.Cards.Add(MoveTemp(D));
  }
  const FS08HeroEntry* H = UmRmHero(Flow->GetHeroes(), Me->HeroId);
  const FString Name = H ? H->Name : FString();
  const FUmInspectModel M = UmInspect::FromList(List, UmPortrait::SlugOf(Name), Name, EUmInspectSource::Room);
  S->Open(M);
  PlayScreenSound(FName(TEXT("UI-PANEL-OPEN")));
  FS08Trace::Write(UmInspect::OpenLine(M));
}

// ------------------------------------------------------------------------------------------------ route

FString AS08FlowGameMode::UmRoomRoute() {
  if (!UmRoomRt.IsValid() || !Flow.IsValid() || bAuto) return FString();
  FUmRoomRuntime& R = *UmRoomRt;
  const ES08Stage Stage = Flow->GetStage();
  const double Now = UmRmNowMs();
  if (Stage != R.LastStage) {
    if (Stage == ES08Stage::Started) {
      // the start: the host who pressed «Начать» counts 3-2-1; a guest (any other start) sees «Партия начинается…»
      if (R.LastStage == ES08Stage::Room && R.bRoomShown && R.Room.IsValid()) {
        R.Phase = (R.bStartPressed && Flow->GetRoom().IsHost(Flow->GetUserId())) ? EUmRoomPhase::Countdown : EUmRoomPhase::Starting;
        R.PhaseStartMs = Now;
        R.LastDigit = -1;
        FS08Trace::Write(FString::Printf(TEXT("ROOM start seen phase=%s"), R.Phase == EUmRoomPhase::Countdown ? TEXT("countdown") : TEXT("starting")));
      } else {
        R.Phase = EUmRoomPhase::Room;
      }
      R.bLoadingDone = !R.Loading.IsValid();
      R.bLoadingShowing = false;
      R.LoadingShownMs = -1.0;
      R.AppliedBase = AppliedCount;
      R.BoardReadyFrames = 0;
      R.LStage = EUmLoadingStage::Connect;
    } else {
      R.Phase = EUmRoomPhase::Room;
      R.bLoadingDone = true;
    }
    if (Stage != ES08Stage::Room) {
      R.bRoomShown = false;
      R.bStartPressed = false;
      R.bBusy = false;
      R.PendingPickHeroId.Reset();
      R.ForcedTakenHeroId.Reset();
      if (Stage != ES08Stage::Started) R.LastOwnHeroId.Reset();  // the countdown keeps it: no second sting
    }
    R.LastStage = Stage;
  }
  if (Stage == ES08Stage::Room) return R.Room.IsValid() ? TEXT("room") : FString();
  if (Stage != ES08Stage::Started) return FString();
  if (R.Phase == EUmRoomPhase::Countdown) {
    const int32 Digit = UmRoom::CountDigit(Now - R.PhaseStartMs);
    if (Digit == 0) {
      R.Phase = EUmRoomPhase::Starting;
      R.PhaseStartMs = Now;
      PlayScreenSound(FName(TEXT("UI-ROOM-COUNT-GO")));  // the host's countdown ended (08: the start sound of the screen)
      FS08Trace::Write(FString::Printf(TEXT("ROOM countdown go t=%.0f"), Now));
    } else if (Digit != R.LastDigit) {
      R.LastDigit = Digit;
      PlayScreenSound(FName(TEXT("UI-ROOM-COUNT")));
      FS08Trace::Write(FString::Printf(TEXT("ROOM countdown n=%d t=%.0f"), Digit, Now));
    }
  }
  if (R.Phase == EUmRoomPhase::Starting && Now - R.PhaseStartMs >= UmRoom::StartingHoldMs) {
    R.Phase = EUmRoomPhase::Room;
    FS08Trace::Write(TEXT("ROOM starting done -> loading"));
  }
  if (R.Phase != EUmRoomPhase::Room && R.Room.IsValid()) return TEXT("room");
  if (!R.bLoadingDone && R.Loading.IsValid()) return TEXT("loading");
  return FString();
}

void AS08FlowGameMode::ApplyUmRoomCanvas(const FVector2D& CanvasSu, bool bClassS, float PxPerSu) {
  if (!UmRoomRt.IsValid()) return;
  FUmRoomRuntime& R = *UmRoomRt;
  if (R.Room.IsValid()) R.Room->ApplyCanvas(CanvasSu, bClassS, PxPerSu);
  if (R.Loading.IsValid()) R.Loading->ApplyCanvas(CanvasSu, bClassS, PxPerSu);
  if (R.Inspect.IsValid()) R.Inspect->ApplyCanvas(CanvasSu, bClassS, PxPerSu);
  if (R.Confirm.IsValid()) R.Confirm->SetCanvas(CanvasSu, bClassS, PxPerSu);
}

// ------------------------------------------------------------------------------------------------ ROOM tick

void AS08FlowGameMode::TickUmRoom(bool bShowing) {
  if (!UmRoomRt.IsValid() || !Flow.IsValid()) return;
  FUmRoomRuntime& R = *UmRoomRt;
  UUmScreenRoom* Scr = R.Room.Get();
  const double Now = UmRmNowMs();
  if (bShowing && Flow->GetStage() == ES08Stage::Room) R.bRoomShown = true;
  if (!bShowing || !Scr) {
    if (UUmScreenInspect* I = R.Inspect.Get(); I && I->IsOpen()) I->Close(TEXT("owner"));
    if (UUmConfirmDialog* D = R.Confirm.Get(); D && D->IsOpen() && Flow->GetStage() != ES08Stage::Room) D->Answer(false);
    R.LastShotKey.Reset();
    TickUmRoomDrive();
    return;
  }
  const FS08RoomState& Room = Flow->GetRoom();
  const FString& Me = Flow->GetUserId();
  const TArray<FS08HeroEntry>& Heroes = Flow->GetHeroes();
  // ---- busy: ends with the room answer, an error, or 8 s
  if (R.bBusy && (UmRmRoomKey(Room) != R.BusyKey || Now - R.BusySinceMs > 8000.0)) {
    if (Now - R.BusySinceMs > 8000.0) FS08Trace::Write(TEXT("ROOM busy timeout"));
    R.bBusy = false;
  }
  if (!R.bBusy) R.PendingPickHeroId.Reset();
  // ---- the seats: the host first (slot 1), the other player second
  const FS08RoomPlayer* HostP = Room.Players.FindByPredicate([&Room](const FS08RoomPlayer& P) { return P.UserId == Room.HostId; });
  const FS08RoomPlayer* OtherP = Room.Players.FindByPredicate([&Room](const FS08RoomPlayer& P) { return P.UserId != Room.HostId; });
  const FS08RoomPlayer* MeP = Room.Players.FindByPredicate([&Me](const FS08RoomPlayer& P) { return P.UserId == Me; });
  const FS08RoomPlayer* OppP = Room.Players.FindByPredicate([&Me](const FS08RoomPlayer& P) { return P.UserId != Me; });
  const bool bVsAi = Room.Mode == TEXT("VS_AI");
  // ---- the details: the roster cards and every seat hero (adminHero + cardList, once each)
  TArray<FString> Ids;
  for (const TCHAR* Name : UmRmRoster) {
    if (const FS08HeroEntry* H = Heroes.FindByPredicate([Name](const FS08HeroEntry& E) { return E.Name == Name; })) Ids.AddUnique(H->Id);
  }
  TArray<FString> Ask = Ids;
  for (const FS08RoomPlayer& P : Room.Players) {
    if (!P.HeroId.IsEmpty()) Ask.AddUnique(P.HeroId);
  }
  for (const FString& Id : Ask) {
    if (R.Asked.Contains(Id)) continue;
    R.Asked.Add(Id);
    Flow->FetchHeroDetails(Id);
    Flow->FetchHeroDeck(Id);
  }
  // ---- the hero sting: the server confirmed the own pick (08: PlayHeroSelectSting on the confirmation)
  const FString OwnHero = MeP ? MeP->HeroId : FString();
  if (OwnHero != R.LastOwnHeroId) {
    if (!OwnHero.IsEmpty() && Flow->GetStage() == ES08Stage::Room) {
      if (const FS08HeroEntry* H = UmRmHero(Heroes, OwnHero)) {
        PlayHeroSelectSting(H->Name);
        FS08Trace::Write(FString::Printf(TEXT("ROOM picked hero=%s sting=1"), *OwnHero));
      }
      R.ForcedTakenHeroId.Reset();
    }
    R.LastOwnHeroId = OwnHero;
  }
  if (OppP && OppP->HeroId == R.ForcedTakenHeroId) R.ForcedTakenHeroId.Reset();  // the room answer says it now
  // ---- the model
  auto Slot = [&](const FS08RoomPlayer* P, bool bHostSeat) {
    FUmRoomSlotModel S;
    if (!P) {
      S.Seat = (!bHostSeat && bVsAi) ? EUmRoomSeat::Ai : EUmRoomSeat::Waiting;
      S.bReady = S.Seat == EUmRoomSeat::Ai;  // the server seats the bot ready on startGame (ВР-VS4-SC17-01)
      return S;
    }
    S.Seat = EUmRoomSeat::Player;
    S.Username = P->Username;
    S.bHost = bHostSeat;
    S.bReady = P->bIsReady;
    if (const FS08HeroEntry* H = UmRmHero(Heroes, P->HeroId)) {
      S.HeroName = H->Name;
      S.HeroKey = FName(*UmPortrait::SlugOf(H->Name));
    }
    if (const FS08FlowController::FHeroDetails* D = Flow->FindHeroDetails(P->HeroId)) {
      S.bDetails = true;
      S.Hp = D->Health;
      S.Move = D->Movement;
      if (D->Sidekicks.Num()) {
        S.SidekickName = D->Sidekicks[0].Name;
        S.SidekickCount = D->Sidekicks[0].Count;
        S.SidekickHp = D->Sidekicks[0].Health;
      }
    }
    return S;
  };
  FUmRoomModel M;
  M.Code = Room.Code;
  M.bVsAi = bVsAi;
  M.bHost = Room.IsHost(Me);
  M.BoardId = Room.BoardId;
  const TMap<FString, FString>& Names = Flow->GetBoardNames();
  M.BoardNames[0] = UmRmBoardName(Names, UmLobby::MarmorealId);
  M.BoardNames[1] = UmRmBoardName(Names, UmLobby::SarpedonId);
  M.Slots[0] = Slot(HostP, true);
  M.Slots[1] = Slot(OtherP, false);
  M.OwnHeroId = OwnHero;
  M.bOwnReady = MeP && MeP->bIsReady;
  M.bOppPresent = OppP != nullptr || bVsAi;
  M.bOppHero = (OppP && !OppP->HeroId.IsEmpty()) || bVsAi;
  M.bOppReady = (OppP && OppP->bIsReady) || bVsAi;
  M.bBusy = R.bBusy;
  if (!OwnHero.IsEmpty()) {
    if (const TArray<FS08FlowController::FHeroDeckCard>* Deck = Flow->FindHeroDeck(OwnHero)) {
      M.DeckCount = 0;
      for (const FS08FlowController::FHeroDeckCard& C : *Deck) M.DeckCount += C.Count;
    }
  }
  for (const FString& Id : Ids) {
    const FS08HeroEntry* H = UmRmHero(Heroes, Id);
    if (!H) continue;
    FUmHeroCardModel C;
    C.HeroId = Id;
    C.Name = H->Name;
    C.Key = FName(*UmPortrait::SlugOf(H->Name));
    if (const FS08FlowController::FHeroDetails* D = Flow->FindHeroDetails(Id)) {
      C.bDetails = true;
      C.Hp = D->Health;
      C.Move = D->Movement;
      C.AttackType = D->AttackType;
      C.Ability = D->Ability;
      if (D->Sidekicks.Num()) {
        const FS08FlowController::FHeroSidekick& K = D->Sidekicks[0];
        C.SidekickName = K.Name;
        C.SidekickKey = FName(*(C.Key.ToString() + TEXT("/") + UmPortrait::SlugOf(K.Name)));
        C.SidekickCount = K.Count;
        C.SidekickHp = K.Health;
        C.SidekickAttack = K.AttackType;
      }
    }
    const bool bTaken = (OppP && OppP->HeroId == Id) || R.ForcedTakenHeroId == Id;
    C.State = Id == OwnHero ? EUmHeroCardState::Picked : bTaken ? EUmHeroCardState::Taken
              : C.bDetails  ? EUmHeroCardState::Normal
                            : EUmHeroCardState::Loading;
    C.bEnabled = !R.bBusy;
    M.Heroes.Add(MoveTemp(C));
  }
  Scr->ApplyModel(M);
  Scr->SetPhase(R.Phase, R.Phase == EUmRoomPhase::Countdown ? FMath::Max(1, R.LastDigit) : 0);
  if (Room.BoardId != R.LastBoardTraced) {
    R.LastBoardTraced = Room.BoardId;
    FS08Trace::Write(FString::Printf(TEXT("ROOM board=%s"), *Room.BoardId));
  }
  // ---- the keys of the open modals (04 §1: the input outside a modal is closed)
  if (APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr) {
    UUmScreenInspect* Insp = R.Inspect.Get();
    UUmConfirmDialog* Dlg = R.Confirm.Get();
    if (Insp && Insp->IsOpen()) {
      for (const FKey& K : {EKeys::Escape, EKeys::I, EKeys::Tab, EKeys::BackSpace}) {
        if (PC->WasInputKeyJustPressed(K)) Insp->HandleKey(K);
      }
    } else if (Dlg && Dlg->IsOpen() && PC->WasInputKeyJustPressed(EKeys::Escape)) {
      Dlg->HandleEscape();
    }
  }
  // ---- the gate lines: once per change of the state and its fields (+ the PORTRAIT lines of the cards and slots)
  {
    const FString Key = Scr->GetScreenState().ToString() + Scr->ShotExtra() + FString::Printf(TEXT("|%d|%s"), M.DeckCount, *M.BoardId);
    if (Key != R.LastShotKey && Scr->GetAlpha() >= 1.0f) {
      R.LastShotKey = Key;
      TArray<FString> Lines;
      Scr->CollectShotLines(Lines);
      Scr->CollectPortraitLines(Lines);
      if (UUmScreenInspect* Insp = R.Inspect.Get(); Insp && Insp->IsOpen()) Insp->CollectShotLines(Lines);
      for (const FString& Line : Lines) FS08Trace::Write(Line);
    }
  }
  // ---- evidence: one frame per sub-state, once it held 300 ms (-S08ScreenShots + -S09ShotDir)
  if (R.Shots < 0) R.Shots = FParse::Param(FCommandLine::Get(), TEXT("S08ScreenShots")) && !S09ShotDir.IsEmpty() ? 1 : 0;
  if (R.Shots == 1 && Scr->GetAlpha() >= 1.0f) {
    FString Sub;
    const UUmScreenInspect* Insp = R.Inspect.Get();
    const UUmConfirmDialog* Dlg = R.Confirm.Get();
    if (R.Phase == EUmRoomPhase::Countdown) {
      Sub = R.LastDigit == 3 ? TEXT("countdown-3") : TEXT("");
    } else if (R.Phase == EUmRoomPhase::Starting) {
      Sub = TEXT("starting");
    } else if (Dlg && Dlg->IsOpen()) {
      Sub = Dlg->GetAlpha() >= 1.0f ? TEXT("leave") : TEXT("");
    } else if (Insp && Insp->IsOpen()) {
      Sub = Insp->GetAlpha() >= 1.0f ? TEXT("deck") : TEXT("");
    } else if (M.Heroes.Num() > 0 && M.Heroes.ContainsByPredicate([](const FUmHeroCardModel& C) { return C.bDetails; })) {
      Sub = FString(M.bHost ? TEXT("host-") : TEXT("guest-")) + Scr->GetScreenState().ToString();
      if (M.Heroes.ContainsByPredicate([](const FUmHeroCardModel& C) { return C.State == EUmHeroCardState::Taken; })) Sub += TEXT("-taken");
      if (M.bVsAi) Sub += TEXT("-ai");
      if (M.BoardId == UmLobby::SarpedonId) Sub += TEXT("-sarpedon");
      if (M.bBusy) Sub.Reset();
    }
    if (Sub != R.CandidateSub) {
      R.CandidateSub = Sub;
      R.CandidateSinceMs = Now;
    }
    if (!Sub.IsEmpty() && Now - R.CandidateSinceMs >= 300.0 && !R.ShotKeys.Contains(Sub)) {
      R.ShotKeys.Add(Sub);
      const FString File = TEXT("UI-SCR-ROOM-") + Sub;
      FS08Trace::Write(FString::Printf(TEXT("SCREENSHOT sub=%s file=%s.png"), *File, *File));
      TakeEvidenceShot(S09ShotDir / (File + TEXT(".png")));
    }
  }
  TickUmRoomDrive();
}

// ------------------------------------------------------------------------------------------------ LOADING tick

void AS08FlowGameMode::TickUmLoading(bool bShowing) {
  if (!UmRoomRt.IsValid() || !Flow.IsValid()) return;
  FUmRoomRuntime& R = *UmRoomRt;
  UUmScreenLoading* L = R.Loading.Get();
  if (!L) return;
  const double Now = UmRmNowMs();
  if (!bShowing) {
    if (R.bLoadingShowing) {
      R.bLoadingShowing = false;
      L->PlayHide();
    }
    return;
  }
  const FS08RoomState& Room = Flow->GetRoom();
  auto SetStage = [&R, L, Now](EUmLoadingStage S) {
    if (R.LStage == S && L->GetStage() == S) return;
    R.LStage = S;
    R.LStageMs = Now;
    L->SetStage(S);
    FS08Trace::Write(FString::Printf(TEXT("LOADING stage=%s t=%.0f"), UmLoading::StageName(S), Now - R.LoadingShownMs));
  };
  if (!R.bLoadingShowing) {
    R.bLoadingShowing = true;
    R.LoadingShownMs = Now;
    R.LStage = EUmLoadingStage::Connect;
    R.LStageMs = Now;
    R.LastLoadingShotKey.Reset();
    L->SetStage(EUmLoadingStage::Connect);
    // the sides: the viewer left, the opponent right (ВР-VS5-SC19-01); database names, never declined
    const FString& Me = Flow->GetUserId();
    FUmLoadingSide Sides[2];
    for (const FS08RoomPlayer& P : Room.Players) {
      FUmLoadingSide& S = Sides[P.UserId == Me ? 0 : 1];
      S.Nick = P.Username;
      if (const FS08HeroEntry* H = UmRmHero(Flow->GetHeroes(), P.HeroId)) {
        S.HeroName = H->Name;
        S.HeroKey = FName(*UmPortrait::SlugOf(H->Name));
      }
    }
    if (Room.Mode == TEXT("VS_AI") && Sides[1].Nick.IsEmpty()) Sides[1].Nick = UmLobby::AiBotName;
    L->SetSides(Sides[0], Sides[1], Room.BoardId, UmRmBoardName(Flow->GetBoardNames(), Room.BoardId));
    FS08Trace::Write(FString::Printf(TEXT("LOADING shown game=%s board=%s players=%d"), *Room.GameId, *Room.BoardId, Room.Players.Num()));
    for (const FString& Line : L->GetPortraitLines()) FS08Trace::Write(Line);
    Flow->FetchGameSequence();
  }
  // ---- ВР-VS7-32: another map never shows through - opaque until the scene under is the room's board
  L->SetVeilOpaque(!(BoardActor || Room.BoardId == UmLobby::MarmorealId));
  // ---- the stages (each reads at least 600 ms, ВР-VS7-31)
  const bool bApplied = AppliedCount > R.AppliedBase;
  const bool bBoard = bApplied && BoardActor && BoardActor->GetFighters().Num() > 0;
  R.BoardReadyFrames = bBoard ? R.BoardReadyFrames + 1 : 0;
  const bool bHeld = Now - R.LStageMs >= UmLoading::MinStageMs;
  if (R.LStage == EUmLoadingStage::Connect) {
    const FS08FlowController::EBootQuery Q = Flow->GetGameSequenceState();
    if (bHeld && (Q == FS08FlowController::EBootQuery::Done || Q == FS08FlowController::EBootQuery::Failed || bApplied)) SetStage(EUmLoadingStage::State);
  } else if (R.LStage == EUmLoadingStage::State) {
    if (bHeld && bApplied) SetStage(EUmLoadingStage::Board);
  } else if (R.LStage == EUmLoadingStage::Board) {
    if (bHeld && R.BoardReadyFrames >= 3) {
      R.bLoadingDone = true;
      FS08Trace::Write(FString::Printf(TEXT("LOADING done t=%.0f fighters=%d board=%s"), Now - R.LoadingShownMs,
                                       BoardActor ? BoardActor->GetFighters().Num() : 0, *Room.BoardId));
    }
  } else if (R.LStage == EUmLoadingStage::Error && bApplied) {
    SetStage(EUmLoadingStage::Board);  // a late answer: the match loaded after all
  }
  if (R.LStage != EUmLoadingStage::Error && !bApplied && Now - R.LoadingShownMs >= UmLoading::ErrorAfterMs) {
    SetStage(EUmLoadingStage::Error);
    PlayScreenSound(FName(TEXT("UI-NET-LOST")));
    FS08Trace::Write(FString::Printf(TEXT("LOADING error waited=%.0f"), Now - R.LoadingShownMs));
  }
  // ---- the gate line once per stage
  {
    const FString Key = L->GetScreenState().ToString() + L->ShotExtra();
    if (Key != R.LastLoadingShotKey && L->GetAlpha() >= 1.0f) {
      R.LastLoadingShotKey = Key;
      TArray<FString> Lines;
      L->CollectShotLines(Lines);
      for (const FString& Line : Lines) FS08Trace::Write(Line);
    }
  }
  // the stage frames: the base screen queue (UI-SCR-LOADING-<stage>.png, ВР-SC14) - every stage holds >= 600 ms
}

// ------------------------------------------------------------------------------------------------ the evidence drive

void AS08FlowGameMode::TickUmRoomDrive() {
  if (!UmRoomRt.IsValid() || !Flow.IsValid() || bAuto) return;
  FUmRoomRuntime& R = *UmRoomRt;
  if (R.Steps.Num() == 0 || R.Step >= R.Steps.Num()) return;
  UUmScreenRoom* Scr = R.Room.Get();
  // the drive starts once the ROOM showed its cards
  if (!R.bDriveArmed) {
    if (!Scr || !Scr->IsShown() || Scr->GetAlpha() < 1.0f || Flow->GetStage() != ES08Stage::Room) return;
    if (!Scr->GetModel().Heroes.ContainsByPredicate([](const FUmHeroCardModel& C) { return C.bDetails; })) return;
    R.bDriveArmed = true;
    FS08Trace::Write(FString::Printf(TEXT("ROOM-DRIVE armed plan=%s"), *R.Drive));
  }
  const double Now = UmRmNowMs();
  if (R.StepAtMs < 0.0) R.StepAtMs = Now;
  const FString& S = R.Steps[R.Step];
  auto Done = [&R, &S]() {
    FS08Trace::Write(FString::Printf(TEXT("ROOM-DRIVE step=%s"), *S));
    ++R.Step;
    R.StepAtMs = -1.0;
  };
  const FUmRoomModel* M = Scr ? &Scr->GetModel() : nullptr;
  auto HeroIdOf = [this](const TCHAR* Name) {
    const FS08HeroEntry* H = Flow->GetHeroes().FindByPredicate([Name](const FS08HeroEntry& E) { return E.Name == Name; });
    return H ? H->Id : FString();
  };
  if (S == TEXT("hold")) {
    if (Now - R.StepAtMs >= 2500.0) Done();
  } else if (S.StartsWith(TEXT("wait"))) {
    if (Now - R.StepAtMs >= 1000.0 * FCString::Atoi(*S.RightChop(4))) Done();
  } else if (S == TEXT("opp") || S == TEXT("opphero") || S == TEXT("oppready")) {
    const bool bOk = M && (S == TEXT("opp") ? M->bOppPresent : S == TEXT("opphero") ? M->bOppHero : M->bOppReady);
    if (bOk || Now - R.StepAtMs > 120000.0) Done();
  } else if (S.StartsWith(TEXT("pick-")) || S.StartsWith(TEXT("forcepick-"))) {
    if (Now - R.StepAtMs < 800.0 || !M) return;
    const TCHAR* Name = S.EndsWith(TEXT("medusa")) ? TEXT("Medusa") : TEXT("King Arthur");
    if (S.StartsWith(TEXT("forcepick-"))) {
      // the server refusal proof: SelectHero of a hero the opponent holds (the card has no button for it)
      const FString Id = HeroIdOf(Name);
      R.bBusy = true;
      R.BusySinceMs = Now;
      R.BusyKey = UmRmRoomKey(Flow->GetRoom());
      R.PendingPickHeroId = Id;
      FS08Trace::Write(FString::Printf(TEXT("ROOM pick hero=%s forced=1"), *Id));
      Flow->SelectHero(Id);
    } else {
      for (int32 I = 0; I < M->Heroes.Num(); ++I) {
        if (M->Heroes[I].Name == Name) Scr->SimulatePress(FName(*FString::Printf(TEXT("screens.room.hero.pick.%d"), I)));
      }
    }
    Done();
  } else if (S == TEXT("deck") || S == TEXT("ready") || S == TEXT("start") || S == TEXT("leave") || S == TEXT("copy")) {
    if (Now - R.StepAtMs < 800.0 || !Scr || (M && M->bBusy)) return;
    Scr->SimulatePress(FName(S == TEXT("deck") ? TEXT("screens.room.deck.view") : S == TEXT("ready") ? TEXT("screens.room.ready")
                             : S == TEXT("start") ? TEXT("screens.room.start") : S == TEXT("leave") ? TEXT("screens.room.leave")
                                                  : TEXT("screens.room.code.copy")));
    Done();
  } else if (S == TEXT("deckclose")) {
    if (Now - R.StepAtMs < 2500.0) return;
    if (UUmScreenInspect* Insp = R.Inspect.Get(); Insp && Insp->IsOpen()) Insp->Close(TEXT("drive"));
    Done();
  } else if (S == TEXT("leaveno") || S == TEXT("leaveyes")) {
    if (Now - R.StepAtMs < 2500.0) return;
    if (UUmConfirmDialog* Dlg = R.Confirm.Get(); Dlg && Dlg->IsOpen()) Dlg->Answer(S == TEXT("leaveyes"));
    Done();
  } else if (S == TEXT("errretry") || S == TEXT("errlobby")) {
    UUmScreenLoading* L = R.Loading.Get();
    if (!L || L->GetStage() != EUmLoadingStage::Error) {
      if (Now - R.StepAtMs > 60000.0) Done();
      return;
    }
    if (R.ErrHeldMs < 0.0) R.ErrHeldMs = Now;
    if (Now - R.ErrHeldMs < 2500.0) return;
    L->SimulatePress(FName(S == TEXT("errretry") ? TEXT("common.btn.retry") : TEXT("common.btn.lobby")));
    R.ErrHeldMs = -1.0;
    Done();
  } else if (S == TEXT("game")) {
    // the match on screen (the loading done), then 5 s of it
    const bool bGame = Flow->GetStage() == ES08Stage::Started && R.bLoadingDone && R.Phase == EUmRoomPhase::Room;
    if (!bGame) {
      R.StepAtMs = Now;
      return;
    }
    if (Now - R.StepAtMs >= 5000.0) Done();
  } else if (S == TEXT("exit")) {
    FS08Trace::Write(TEXT("ROOM-DRIVE done"));
    AutoExitAfter = Elapsed + 1.0f;
    ++R.Step;
  } else {
    FS08Trace::Write(FString::Printf(TEXT("ROOM-DRIVE unknown step=%s"), *S));
    ++R.Step;
  }
}

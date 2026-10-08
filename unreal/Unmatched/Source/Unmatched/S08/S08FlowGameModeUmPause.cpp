// VS-7 S4 (docs/game-design/visual/05-production-plan.md §3 VS-7, H16; screens.csv SC-24...SC-30; 04-hud-spec.md §1.8): the
// game-mode side of PAUSE and the settings (UI/UmScreenPause.h, UI/UmSettingRow.h).
//
//   open      Esc with nothing to close in GAME (the move input's "pause" answer), «≡» in TOP, the «≡» of the LOBBY / ROOM
//             headers and Esc there (no other modal open). The context follows the route: GAME, LOBBY (no leave button),
//             ROOM («Выйти из комнаты» -> the room's own leave dialog). Opening: UI-PANEL-OPEN + SetAudioPaused(true)
//             (the audio side ducks the music -10 dB); closing (Esc, «Продолжить»): UI-PANEL-CLOSE + SetAudioPaused(false).
//             The match on the server never stops: the timers run, the snapshots keep applying under the veil.
//   leave     GAME: «Покинуть партию» -> UUmConfirmDialog «Покинуть партию» / «Партия прервётся для обоих игроков» ->
//             UI-PAUSE-EXIT + leaveGame; disabled with why.syncing while a command is in flight.
//   settings  a row commit = s08.Settings name + value: US08UserSettings::ApplySetting + Save (OnChanged: the volumes, the
//             motion settings and the UI scale apply without a restart - their own listeners), 'SETTINGS set <k>=<v>
//             source=pause'; language = UmText::SetUiLanguage (the table texts re-resolve in the next frame); graphics =
//             GameUserSettings overall scalability 2 | 1 | 0 with the resolution quality kept at 100 (r.ScreenPercentage
//             and the 60 FPS cap untouched, AGENTS.md), saved, then one 'RENDER … tag=SETTINGS' line.
//   language  at the start: -S08Lang=ru|en|pseudo, else the saved language unless the run passes -culture= (the set-I
//             scripts) - 'SETTINGS language=<l> culture=<c> pseudo=<0|1> source=<flag|saved|culture>'.
//   evidence  review tooling: -S08PauseDrive=<step+step..>: open, close, wait<N>, inlobby / inroom / ingame (wait for that
//             route), tab-<sound|interface|game|graphics>, scroll, top, <key>.<value> (a row through its own input path:
//             master.50, masterMute.1, language.en, uiScale.150, keyHints.off, speed.none, reduced.1, graphics.0, ...),
//             leave, leaveno, leaveyes, exit. With -S08ScreenShots and -S09ShotDir one frame per sub-state
//             UI-SCR-PAUSE-<context>-<tab|confirm>[-defense][-syncing][-scrolled][-<lang>][-ui<n>][-gfx<n>].png after 300 ms.
#include "S08FlowGameMode.h"

#include "S08ArtLook.h"
#include "S08BoardActor.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "S08UserSettings.h"
#include "UI/UmConfirmDialog.h"
#include "UI/UmHudRoot.h"
#include "UI/UmHudScale.h"
#include "UI/UmScreenPause.h"
#include "UI/UmText.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/GameUserSettings.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Scalability.h"

/** Per-run state of PAUSE (owned by the game mode). */
struct FUmPauseRuntime {
  TWeakObjectPtr<UUmScreenPause> Pause;
  TWeakObjectPtr<UUmConfirmDialog> Confirm;
  EUmPauseContext Context = EUmPauseContext::Game;
  EUmPauseTab Tab = EUmPauseTab::Sound;
  FString Route;
  bool bOpen = false;
  bool bInTick = false;
  uint64 OpenFrame = 0;
  uint64 EscFrame = 0;
  FIntPoint LastCanvas = FIntPoint(-1, -1);
  float LastPx = -1.0f;
  FString LastShotKey;
  // evidence
  int32 Shots = -1;
  TSet<FString> ShotKeys;
  FString CandidateSub;
  double CandidateSinceMs = -1.0;
  FString Drive;
  TArray<FString> Steps;
  int32 Step = 0;
  double StepAtMs = -1.0;
};

namespace {
double UmPsNowMs() { return FPlatformTime::Seconds() * 1000.0; }

FString UmPsCulture() {
  return FInternationalization::Get().GetCurrentLanguage()->GetTwoLetterISOLanguageName() == TEXT("en") ? TEXT("en") : TEXT("ru");
}

/** The overall level of the scalability groups (resolution aside): 0..3, -1 when they differ. */
int32 UmPsGraphicsLevel() {
  const Scalability::FQualityLevels Q = Scalability::GetQualityLevels();
  const int32 L = Q.ViewDistanceQuality;
  const bool bSame = Q.AntiAliasingQuality == L && Q.ShadowQuality == L && Q.GlobalIlluminationQuality == L && Q.ReflectionQuality == L &&
                     Q.PostProcessQuality == L && Q.TextureQuality == L && Q.EffectsQuality == L && Q.FoliageQuality == L &&
                     Q.ShadingQuality == L;
  return bSame ? L : -1;
}
}  // namespace

// ------------------------------------------------------------------------------------------------ build

void AS08FlowGameMode::BuildUmPause() {
  if (!UmPauseRt.IsValid()) UmPauseRt = MakeShared<FUmPauseRuntime>();
  FUmPauseRuntime& R = *UmPauseRt;
  FParse::Value(FCommandLine::Get(), TEXT("S08PauseDrive="), R.Drive);
  R.Drive.ParseIntoArray(R.Steps, TEXT("+"), true);
  // ---- SC-26: the language of the run (before the screens draw their first texts)
  {
    const US08UserSettings* Settings = US08UserSettings::Get();
    const TCHAR* Cmd = FCommandLine::Get();
    FString Flag, CultureFlag;
    const bool bFlag = FParse::Value(Cmd, TEXT("S08Lang="), Flag);
    const bool bCulture = FParse::Value(Cmd, TEXT("culture="), CultureFlag);
    const FString Lang = US08UserSettings::ResolveLanguage(Settings ? Settings->Language : FString(TEXT("ru")), Cmd);
    const TCHAR* Source = bFlag ? TEXT("flag") : bCulture ? TEXT("culture") : TEXT("saved");
    if (bFlag || !bCulture) {
      UmText::SetUiLanguage(Lang == TEXT("pseudo") ? TEXT("ru") : *Lang);
      FTextLocalizationManager::Get().WaitForAsyncTasks();
    }
    FS08Trace::Write(FString::Printf(TEXT("SETTINGS language=%s culture=%s pseudo=%d source=%s"), *Lang, *UmPsCulture(),
                                     UmText::IsPseudo() ? 1 : 0, Source));
  }
  if (!UmHudRoot || !UmHudRoot->Modals) return;
  const S08ArtLook::FS08SlateHudBlocks Blocks = S08ArtLook::SlateHudBlocks();
  if (Blocks.IsSlate(FName(TEXT("pause")))) {
    FS08Trace::Write(TEXT("HUD-SCREENS pause=slate reason=-S08SlateHud"));
    return;
  }
  UUmScreenPause* P = CreateWidget<UUmScreenPause>(UmHudRoot, UUmScreenPause::WidgetClass());
  if (!P) return;
  if (UOverlaySlot* O = UmHudRoot->Modals->AddChildToOverlay(P)) {
    O->SetHorizontalAlignment(HAlign_Fill);
    O->SetVerticalAlignment(VAlign_Fill);
  }
  const TWeakObjectPtr<AS08FlowGameMode> WeakThis(this);
  UUmScreenPause::FInput In;
  In.OnContinue = [WeakThis]() {
    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->CloseUmPause(TEXT("continue"));
  };
  In.OnLeave = [WeakThis]() {
    AS08FlowGameMode* Self = WeakThis.Get();
    if (!Self || !Self->UmPauseRt.IsValid()) return;
    FUmPauseRuntime& S = *Self->UmPauseRt;
    if (S.Context == EUmPauseContext::Room) {
      Self->CloseUmPause(TEXT("room-leave"));
      Self->OpenUmRoomLeave();  // the room's own dialog «Выйти из комнаты?»
      return;
    }
    UUmConfirmDialog* Dlg = S.Confirm.Get();
    if (!Dlg) return;
    UUmConfirmDialog::FRequest Req;
    Req.OwnerUiId = TEXT("UI-SCR-PAUSE");
    Req.Title = UmText::Get(EUmTable::Screens, TEXT("screens.pause.leave"));
    Req.Message = UmText::Get(EUmTable::Screens, TEXT("screens.pause.leave.confirm"));
    Req.OnConfirm = [WeakThis]() {
      AS08FlowGameMode* Me = WeakThis.Get();
      if (!Me || !Me->Flow.IsValid()) return;
      Me->PlayScreenSound(FName(TEXT("UI-PAUSE-EXIT")));
      Me->CloseUmPause(TEXT("leave"));
      FS08Trace::Write(TEXT("PAUSE leave confirmed (leaveGame)"));
      Me->Flow->LeaveRoom();
    };
    Req.OnCancel = [WeakThis]() {
      if (AS08FlowGameMode* Me = WeakThis.Get()) Me->PlayScreenSound(FName(TEXT("UI-PANEL-CLOSE")));
      FS08Trace::Write(TEXT("PAUSE leave cancelled"));
    };
    Dlg->Open(MoveTemp(Req));
    Self->PlayScreenSound(FName(TEXT("UI-PANEL-OPEN")));
    FS08Trace::Write(TEXT("PAUSE leave asked"));
  };
  In.OnCommit = [WeakThis](FName Key, const FString& Value) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->ApplyUmPauseSetting(Key, Value);
  };
  In.OnSound = [WeakThis](FName Bank) {
    if (AS08FlowGameMode* Self = WeakThis.Get()) Self->PlayScreenSound(Bank);
  };
  In.OnTab = [WeakThis](EUmPauseTab Tab) {
    if (AS08FlowGameMode* Self = WeakThis.Get(); Self && Self->UmPauseRt.IsValid()) Self->UmPauseRt->Tab = Tab;
    FS08Trace::Write(FString::Printf(TEXT("PAUSE tab=%s"), UmPause::TabName(Tab)));
  };
  P->SetInput(HudPress, MoveTemp(In));
  R.Pause = P;
  if (UUmConfirmDialog* Dlg = CreateWidget<UUmConfirmDialog>(UmHudRoot, UUmConfirmDialog::WidgetClass())) {
    if (UOverlaySlot* O = UmHudRoot->Modals->AddChildToOverlay(Dlg)) {
      O->SetHorizontalAlignment(HAlign_Fill);
      O->SetVerticalAlignment(VAlign_Fill);
    }
    Dlg->SetInput(HudPress);
    R.Confirm = Dlg;
  }
  FString Missing;
  FS08Trace::Write(FString::Printf(TEXT("HUD-SCREENS pause=%s pauseParts=%d missing=%s confirm=%d drive=%s"), *P->SourceName(),
                                   P->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing, R.Confirm.IsValid() ? 1 : 0,
                                   R.Drive.IsEmpty() ? TEXT("-") : *R.Drive));
}

// ------------------------------------------------------------------------------------------------ open / close

bool AS08FlowGameMode::UmPauseShown() const { return UmPauseRt.IsValid() && UmPauseRt->bOpen; }

bool AS08FlowGameMode::OpenUmPause(const TCHAR* Why) {
  if (!UmPauseRt.IsValid() || !UmPauseRt->Pause.IsValid()) return false;
  FUmPauseRuntime& R = *UmPauseRt;
  if (R.bOpen) return true;
  // the context follows the route: no PAUSE over BOOT / LOGIN / the loading
  if (R.Route == TEXT("lobby")) {
    R.Context = EUmPauseContext::Lobby;
  } else if (R.Route == TEXT("room")) {
    R.Context = EUmPauseContext::Room;
  } else if (R.Route.IsEmpty() && Flow.IsValid() && Flow->GetStage() == ES08Stage::Started) {
    R.Context = EUmPauseContext::Game;
  } else {
    FS08Trace::Write(FString::Printf(TEXT("PAUSE refused why=%s route=%s"), Why, R.Route.IsEmpty() ? TEXT("game") : *R.Route));
    return false;
  }
  R.bOpen = true;
  R.OpenFrame = GFrameCounter;
  R.LastShotKey.Reset();
  UUmScreenPause* P = R.Pause.Get();
  const FUmHudScaleState& Scale = UmHudScale::Current();
  if (Scale.CanvasSu.X > 0) {
    R.LastCanvas = Scale.CanvasSu;
    R.LastPx = Scale.PxPerSu();
    P->ApplyCanvas(FVector2D(Scale.CanvasSu.X, Scale.CanvasSu.Y), Scale.bClassS, Scale.PxPerSu());
  }
  P->SetTab(R.Tab);
  P->ScrollTo(0.0f);
  {
    TGuardValue<bool> Nested(R.bInTick, true);
    TickUmPause(R.Route);  // the model before the first frame (no Esc, no drive step in this call)
  }
  P->PlayShow();
  SetAudioPaused(true);   // the audio side ducks the music -10 dB (08-screen-audio-hooks SC-24)
  PlayScreenSound(FName(TEXT("UI-PANEL-OPEN")));
  FS08Trace::Write(FString::Printf(TEXT("PAUSE open why=%s context=%s tab=%s"), Why, UmPause::ContextName(R.Context), UmPause::TabName(R.Tab)));
  return true;
}

void AS08FlowGameMode::CloseUmPause(const TCHAR* Why) {
  if (!UmPauseRt.IsValid() || !UmPauseRt->bOpen) return;
  FUmPauseRuntime& R = *UmPauseRt;
  R.bOpen = false;
  if (UUmConfirmDialog* Dlg = R.Confirm.Get(); Dlg && Dlg->IsOpen()) Dlg->Answer(false);
  if (UUmScreenPause* P = R.Pause.Get()) P->PlayHide();
  SetAudioPaused(false);
  if (FCString::Strcmp(Why, TEXT("leave")) != 0) PlayScreenSound(FName(TEXT("UI-PANEL-CLOSE")));
  FS08Trace::Write(FString::Printf(TEXT("PAUSE close why=%s"), Why));
}

bool AS08FlowGameMode::UmPauseOwnsInput() {
  if (!UmPauseRt.IsValid()) return false;
  // the open modal owns the keyboard and the board (04 §1); the Esc that closed it is not Esc of the board too
  return UmPauseRt->bOpen || UmPauseRt->EscFrame == GFrameCounter;
}

// ------------------------------------------------------------------------------------------------ settings

void AS08FlowGameMode::ApplyUmPauseSetting(FName Key, const FString& Value) {
  US08UserSettings* Settings = US08UserSettings::Get();
  if (!Settings) return;
  const FString K = Key.ToString();
  if (K == TEXT("graphics")) {
    // SC-30 (ВР-H10): GameUserSettings overall scalability; the resolution quality stays 100 - r.ScreenPercentage, the
    // FPS cap and dynamic resolution are never touched (AGENTS.md «Unreal GPU load», ВР-VS7-50)
    const int32 Level = FMath::Clamp(FCString::Atoi(*Value), 0, 2);
    UGameUserSettings* Gus = GEngine ? GEngine->GetGameUserSettings() : nullptr;
    if (!Gus) return;
    Gus->SetOverallScalabilityLevel(Level);
    Gus->ScalabilityQuality.ResolutionQuality = 100.0f;
    Scalability::SetQualityLevels(Gus->ScalabilityQuality);
    Gus->SaveSettings();
    FS08Trace::Write(FString::Printf(TEXT("SETTINGS set graphics=%d source=pause"), Level));
    FS08Trace::Write(S08RenderFingerprint(GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(), TEXT("SETTINGS")));
  } else {
    FString Error;
    if (!Settings->ApplySetting(K, Value, Error)) {
      FS08Trace::Write(FString::Printf(TEXT("SETTINGS refused %s=%s error=%s"), *K, *Value, *Error));
      return;
    }
    FS08Trace::Write(FString::Printf(TEXT("SETTINGS set %s=%s source=pause"), *K, *Value));
    if (K == TEXT("language")) {
      UmText::SetUiLanguage(*Settings->Language);  // the table texts re-resolve; the modal measures them again below
      FTextLocalizationManager::Get().WaitForAsyncTasks();
    }
    Settings->Save();  // OnChanged: the volumes, the motion settings and the UI scale apply without a restart
  }
  if (UmPauseRt.IsValid()) {
    TGuardValue<bool> Nested(UmPauseRt->bInTick, true);
    TickUmPause(UmPauseRt->Route);
  }
}

// ------------------------------------------------------------------------------------------------ tick

void AS08FlowGameMode::TickUmPause(const FString& Route) {
  if (!UmPauseRt.IsValid()) return;
  FUmPauseRuntime& R = *UmPauseRt;
  R.Route = Route;
  const bool bNested = R.bInTick;
  TGuardValue<bool> InTick(R.bInTick, true);
  UUmScreenPause* P = R.Pause.Get();
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  const bool bEsc = !bNested && PC && PC->WasInputKeyJustPressed(EKeys::Escape) && ViewportHasFocus();
  // a route the modal cannot stay on (the match ended, the room started loading): it goes
  if (!bNested && R.bOpen && ((R.Context == EUmPauseContext::Game && (Route != FString() || !Flow.IsValid() || Flow->GetStage() != ES08Stage::Started)) ||
                  (R.Context == EUmPauseContext::Lobby && Route != TEXT("lobby")) ||
                  (R.Context == EUmPauseContext::Room && Route != TEXT("room")))) {
    CloseUmPause(TEXT("route"));
  }
  // ---- Esc: the leave dialog first, then «Продолжить»; on LOBBY / ROOM with no other modal it opens PAUSE (04 §1)
  if (bEsc && P && GFrameCounter != R.OpenFrame) {
    UUmConfirmDialog* Dlg = R.Confirm.Get();
    if (R.bOpen) {
      R.EscFrame = GFrameCounter;
      if (Dlg && Dlg->IsOpen()) {
        Dlg->HandleEscape();
      } else {
        P->HandleEscape();
      }
    } else if (Route == TEXT("lobby") || Route == TEXT("room")) {
      bool bOther = false;
      for (UUmScreenBase* S : UmScreens::LiveScreens()) bOther |= S && S->IsModal() && S->IsShown() && S != P;
      if (!bOther && OpenUmPause(TEXT("esc"))) R.EscFrame = GFrameCounter;
    }
  }
  const double Now = UmPsNowMs();
  UUmConfirmDialog* Dlg = R.Confirm.Get();
  if (P && (R.bOpen || P->GetAlpha() > 0.0f)) {
    // ---- the canvas (a UI scale change re-lays the modal out in the same frame)
    const FUmHudScaleState& Scale = UmHudScale::Current();
    if (Scale.CanvasSu.X > 0 && (Scale.CanvasSu != R.LastCanvas || Scale.PxPerSu() != R.LastPx)) {
      R.LastCanvas = Scale.CanvasSu;
      R.LastPx = Scale.PxPerSu();
      P->ApplyCanvas(FVector2D(Scale.CanvasSu.X, Scale.CanvasSu.Y), Scale.bClassS, Scale.PxPerSu());
      if (R.Confirm.IsValid()) R.Confirm->SetCanvas(FVector2D(Scale.CanvasSu.X, Scale.CanvasSu.Y), Scale.bClassS, Scale.PxPerSu());
    }
    // ---- the model: the context, the open defense window, a command in flight, the current values
    const US08UserSettings* Settings = US08UserSettings::Get();
    FUmPauseModel M = P->GetModel();
    M.Context = R.Context;
    M.DefenseSeconds = -1;
    M.bSyncing = false;
    if (R.Context == EUmPauseContext::Game) {
      const FS08CombatInfo& Combat = CommandUi.Combat;
      if (Combat.bPresent && Hud.Phase == TEXT("COMBAT") && Combat.bHasTimeoutAt && !Combat.bRevealed) {
        M.DefenseSeconds = FMath::Clamp(FMath::CeilToInt(Combat.SecondsUntilDeadline()), 0, 999);  // combatInfo.timeoutAt
      }
      M.bSyncing = HudBusyReason().IsSet();
    } else if (R.Context == EUmPauseContext::Room) {
      M.bSyncing = UmRoomBusy();
    }
    if (Settings) {
      const FS08AudioSettings A = Settings->GetSavedAudio();
      M.Master = A.MasterPercent;
      M.bMasterMuted = A.bMasterMuted;
      M.Music = A.MusicPercent;
      M.Sfx = A.SfxPercent;
      M.Ui = A.UiPercent;
      M.Vo = A.VoPercent;
      M.Ambience = A.AmbiencePercent;
      M.bAmbienceMuted = A.bAmbienceMuted;
      M.bSubtitles = A.bSubtitles;
      M.bDescribeSounds = A.bDescribeSounds;
      M.UiScale = Settings->GetSavedUiScalePercent();
      M.bRuleHints = Settings->bRuleHints;
      M.KeyHints = US08UserSettings::NormalizeKeyHintsMode(Settings->KeyHintsMode);
      M.bKeyChips = US08UserSettings::KeyHintsShown(M.KeyHints, Settings->CompletedMatches);
      M.AnimSpeed = S08Motion::SpeedName(Settings->GetSavedMotion().Speed);
      M.bReducedMotion = Settings->bReducedMotion;
    }
    M.Language = UmPsCulture();
    M.UiScaleMin = FMath::Min(Scale.Window.X, Scale.Window.Y) > 0 && FMath::Min(Scale.Window.X, Scale.Window.Y) < 1080 ? 100 : 75;  // ВР-62
    M.Graphics = UmPsGraphicsLevel();
    P->ApplyModel(M);
    if (bNested) return;  // a commit or the opening refreshed the model: the gate, the frames and the drive run in the frame's tick
    // ---- the gate lines: once per change of the state and its fields (the leave dialog writes state=confirm)
    const bool bConfirm = Dlg && Dlg->IsOpen();
    const FString Key = P->GetScreenState().ToString() + P->ShotExtra() + (bConfirm ? TEXT("|confirm") : TEXT(""));
    if (R.bOpen && Key != R.LastShotKey && P->GetAlpha() >= 1.0f && (!bConfirm || Dlg->GetAlpha() >= 1.0f)) {
      R.LastShotKey = Key;
      TArray<FString> Lines;
      P->CollectShotLines(Lines);
      if (bConfirm) Dlg->CollectShotLines(Lines);
      for (const FString& Line : Lines) FS08Trace::Write(Line);
    }
    // ---- evidence: one frame per sub-state, once it held 300 ms (-S08ScreenShots + -S09ShotDir)
    if (R.Shots < 0) R.Shots = FParse::Param(FCommandLine::Get(), TEXT("S08ScreenShots")) && !S09ShotDir.IsEmpty() ? 1 : 0;
    if (R.Shots == 1) {
      FString Sub;
      if (R.bOpen && P->GetAlpha() >= 1.0f) {
        Sub = FString(UmPause::ContextName(R.Context)) + TEXT("-") + (bConfirm ? FString(TEXT("confirm")) : P->GetScreenState().ToString());
        if (bConfirm && Dlg->GetAlpha() < 1.0f) Sub.Reset();
        if (!Sub.IsEmpty()) {
          if (M.DefenseSeconds >= 0) Sub += TEXT("-defense");
          if (M.bSyncing) Sub += TEXT("-syncing");
          if (P->GetScrollSu() > 0.5f) Sub += TEXT("-scrolled");
          if (UmText::IsPseudo()) Sub += TEXT("-pseudo");
          else if (M.Language != TEXT("ru")) Sub += TEXT("-") + M.Language;
          if (Scale.UiPercentSet != 100) Sub += FString::Printf(TEXT("-ui%d"), Scale.UiPercentSet);
          if (M.Graphics != 2 && P->GetTab() == EUmPauseTab::Graphics) Sub += FString::Printf(TEXT("-gfx%d"), M.Graphics);
        }
      }
      if (Sub != R.CandidateSub) {
        R.CandidateSub = Sub;
        R.CandidateSinceMs = Now;
      }
      if (!Sub.IsEmpty() && Now - R.CandidateSinceMs >= 300.0 && !R.ShotKeys.Contains(Sub)) {
        R.ShotKeys.Add(Sub);
        const FString File = TEXT("UI-SCR-PAUSE-") + Sub;
        FS08Trace::Write(FString::Printf(TEXT("SCREENSHOT sub=%s file=%s.png"), *File, *File));
        TakeEvidenceShot(S09ShotDir / (File + TEXT(".png")));
      }
    }
  }
  // ---- the evidence drive (review tooling)
  if (bNested || !P || R.Steps.Num() == 0 || R.Step >= R.Steps.Num()) return;
  auto Wait = [&R, Now](double Ms) {
    if (R.StepAtMs < 0.0) R.StepAtMs = Now;
    if (Now - R.StepAtMs < Ms) return false;
    R.StepAtMs = -1.0;
    return true;
  };
  const FString S = R.Steps[R.Step];
  auto Next = [&R, &S]() {
    FS08Trace::Write(FString::Printf(TEXT("PAUSE-DRIVE step=%s"), *S));
    ++R.Step;
  };
  if (S.StartsWith(TEXT("wait"))) {
    if (Wait(FCString::Atod(*S.RightChop(4)))) Next();
    return;
  }
  const bool bInGame = Route.IsEmpty() && Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && Hud.bValid;
  if (S == TEXT("ingame") || S == TEXT("inlobby") || S == TEXT("inroom")) {
    const bool bThere = S == TEXT("ingame") ? bInGame : Route == S.RightChop(2);
    if (!bThere) {
      R.StepAtMs = -1.0;
      return;
    }
    if (Wait(1500.0)) Next();
    return;
  }
  if (S == TEXT("open")) {
    if ((bInGame || Route == TEXT("lobby") || Route == TEXT("room")) && OpenUmPause(TEXT("drive"))) Next();
    return;
  }
  if (!R.bOpen && S != TEXT("exit")) return;
  if (P->GetAlpha() < 1.0f || !Wait(1200.0)) return;  // every state holds for its frame
  if (S == TEXT("close")) {
    P->HandleEscape();
  } else if (S.StartsWith(TEXT("tab-"))) {
    const FString T = S.RightChop(4);
    P->SimulatePress(FName(*(TEXT("screens.pause.tab.") + T)));
  } else if (S == TEXT("scroll")) {
    P->ScrollBy(10000.0f);
  } else if (S == TEXT("top")) {
    P->ScrollTo(0.0f);
  } else if (S == TEXT("leave")) {
    P->SimulatePress(FName(TEXT("screens.pause.leave")));
  } else if (S == TEXT("leaveno") || S == TEXT("leaveyes")) {
    if (Dlg && Dlg->IsOpen()) Dlg->Answer(S == TEXT("leaveyes"));
  } else if (S == TEXT("exit")) {
    AutoExitAfter = Elapsed + 1.0f;
  } else {
    // <key>.<value>: the row of the key (any tab) through its own input path
    FString RowKey, Value;
    if (S.Split(TEXT("."), &RowKey, &Value)) {
      const FName Want(*RowKey);
      for (int32 T = 0; T < 4; ++T) {
        const EUmPauseTab Tab = static_cast<EUmPauseTab>(T);
        for (const FUmSettingRowModel& Row : UmPause::Rows(P->GetModel(), Tab)) {
          if (Row.Key != Want && Row.MuteKey != Want) continue;
          if (P->GetTab() != Tab) {
            P->SimulatePress(FName(*(FString(TEXT("screens.pause.tab.")) + UmPause::TabName(Tab))));
          }
          UUmSettingRow* W = P->FindRow(Row.Key);
          if (!W) break;
          if (Row.MuteKey == Want) {
            if ((Value == TEXT("1")) != Row.bMuted) W->SimulateToggle(true);
          } else if (Row.Kind == EUmSettingKind::Slider) {
            W->SimulateDrag(FCString::Atoi(*Value));
          } else if (Row.Kind == EUmSettingKind::Check) {
            if ((Value == TEXT("1")) != Row.bOn) W->SimulateToggle(false);
          } else {
            W->SimulateChip(Row.ChipValues.IndexOfByKey(Value));
          }
          break;
        }
      }
    }
  }
  Next();
}

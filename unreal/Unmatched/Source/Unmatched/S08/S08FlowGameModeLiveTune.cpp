// ENV-MAPS live tune: the game-mode side of S08LiveTune.h (-ArtLiveTune=<dir> with the -Bench flags). RunRenderBench runs
// its fixture init unchanged (the board, the figures, the camera of a -Bench run), then hands every later tick to
// RunLiveTune: warm-up -> ready.json, then one command at a time from <dir>/cmd-<seq>.json, answered in done-<seq>.json.
// Nothing here runs without the flag.
#include "S08FlowGameMode.h"

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08FighterActor.h"
#include "S08HeroLight.h"
#include "S08LiveTune.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Components/PointLightComponent.h"
#include "DynamicRHI.h"
#include "RenderTimer.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {
int32 LiveGetCvarInt(const TCHAR* Name, int32 Default) {
  const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
  return V ? V->GetInt() : Default;
}

bool LiveSetCvar(const TCHAR* Name, const FString& Value) {
  IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
  if (!V) return false;
  V->Set(*Value, ECVF_SetByConsole);
  return true;
}

FString LiveJson(const TSharedRef<FJsonObject>& Obj) {
  FString Text;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
  FJsonSerializer::Serialize(Obj, Writer);
  return Text;
}
}  // namespace

void AS08FlowGameMode::LiveTuneBeforeBuild() {
  LiveTune = MakeShared<FS08LiveTuneSession>();
  LiveTune->Dir = S08LiveTune::DirFromCommandLine();
  IFileManager::Get().MakeDirectory(*LiveTune->Dir, true);
  FS08Trace::Write(FString::Printf(TEXT("LIVETUNE armed dir=%s protocol=%d (S08LiveTune.h)"), *LiveTune->Dir,
                                   S08LiveTuneSpec::Protocol));
}

void AS08FlowGameMode::LiveTuneAfterBuild(float BenchWarmup, float BenchSettle, float BenchMeasure, float BenchFps,
                                          const FString& Fixture, const FString& HeroId) {
  FS08LiveTuneSession& S = *LiveTune;
  S.Fixture = Fixture;
  S.HeroId = HeroId;
  S.BenchFps = BenchFps;
  S.Clock.BenchWarmup = BenchWarmup;
  S.Clock.BenchSettle = BenchSettle;
  S.Clock.BenchMeasure = BenchMeasure;
  S.Clock.FrameSeconds = BenchFps > 0.0f ? 1.0f / BenchFps : 1.0f / 60.0f;
  FParse::Value(FCommandLine::Get(), S08LiveTuneSpec::BenchGapParam, S.Clock.BenchGap);
  FParse::Value(FCommandLine::Get(), S08LiveTuneSpec::BenchGapLaterParam, S.Clock.BenchGapLater);
  // the clocks of this init tick: the figures spawned now (SyncBoardFromApplied), the world time a -Bench run has here
  S.SpawnElapsed = Elapsed;
  S.InitWorldTime = GetWorld() ? GetWorld()->TimeSeconds : 0.0;
  // the clip positions right after the spawn (PlayHeroClip set the idle phase; no anim tick yet)
  S.ClipStart.Reset();
  S.ClipOffset.Reset();
  if (BoardActor) {
    for (const FS08BoardFighter& F : Fighters) {
      float Pos = 0.0f, Len = 0.0f;
      const AS08FighterActor* A = BoardActor->FindFighterActor(F.Id);
      if (A && A->GetHeroClipTime(Pos, Len)) S.ClipStart.Add(F.Id, Pos);
    }
  }
  const int32 BootEnd = S.BoardBootEnd >= 0 ? S.BoardBootEnd : 0;
  S.BootLines = FS08Trace::JournalSlice(0, BootEnd);
  S.BuildLines = FS08Trace::JournalSlice(BootEnd, FS08Trace::JournalNum());
  FS08Trace::TruncateJournal(0);
  S.WarmupSeconds = BenchWarmup;
  FParse::Value(FCommandLine::Get(), S08LiveTuneSpec::WarmupParam, S.WarmupSeconds);
  FParse::Value(FCommandLine::Get(), TEXT("ArtLiveTuneIdleExit="), S.IdleExitSeconds);
  S.ReadyAt = Elapsed + FMath::Max(S.WarmupSeconds, 0.0f);
  S.LastCommandAt = Elapsed;
  S.State = FS08LiveTuneSession::EState::Warming;
  // a stale ready.json of an earlier session in the same folder must not satisfy the driver
  IFileManager::Get().Delete(*FPaths::Combine(S.Dir, S08LiveTuneSpec::ReadyFile), false, true, true);
  FS08Trace::Write(FString::Printf(
      TEXT("LIVETUNE session dir=%s fixture=%s hero=%s warmup=%.1f idleExit=%.0f bench=(warmup %.1f, settle %.1f, measure %.1f, fps %.0f) bootLines=%d buildLines=%d buildCount=%d"),
      *S.Dir, *FPaths::GetCleanFilename(Fixture), HeroId.IsEmpty() ? TEXT("-") : *HeroId, S.WarmupSeconds,
      S.IdleExitSeconds, BenchWarmup, BenchSettle, BenchMeasure, BenchFps, S.BootLines.Num(), S.BuildLines.Num(),
      BoardActor ? BoardActor->GetBuildCount() : 0));
}

TSharedPtr<FJsonObject> AS08FlowGameMode::LiveTuneState() const {
  const FS08LiveTuneSession& S = *LiveTune;
  TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
  Root->SetNumberField(TEXT("protocol"), S08LiveTuneSpec::Protocol);
  Root->SetNumberField(TEXT("pid"), FPlatformProcess::GetCurrentProcessId());
  Root->SetStringField(TEXT("dir"), S.Dir);
  Root->SetNumberField(TEXT("elapsed"), Elapsed);
  Root->SetNumberField(TEXT("reloads"), S.Reloads);
  Root->SetNumberField(TEXT("shots"), S.Shots);
  Root->SetNumberField(TEXT("lastSeq"), S.LastSeq);
  Root->SetStringField(TEXT("fixture"), FPaths::GetCleanFilename(S.Fixture));
  Root->SetStringField(TEXT("buildConfig"), LexToString(FApp::GetBuildConfiguration()));
  Root->SetBoolField(TEXT("cooked"), FPlatformProperties::RequiresCookedData());
  TSharedRef<FJsonObject> Bench = MakeShared<FJsonObject>();
  Bench->SetNumberField(TEXT("warmup"), S.Clock.BenchWarmup);
  Bench->SetNumberField(TEXT("settle"), S.Clock.BenchSettle);
  Bench->SetNumberField(TEXT("measure"), S.Clock.BenchMeasure);
  Bench->SetNumberField(TEXT("gap"), S.Clock.BenchGap);
  Bench->SetNumberField(TEXT("gapLater"), S.Clock.BenchGapLater);
  Bench->SetNumberField(TEXT("fps"), S.BenchFps);
  Root->SetObjectField(TEXT("bench"), Bench);
  if (!BoardActor) return Root;
  const AS08BoardActor& B = *BoardActor;
  const FS08BoardArtData& Data = B.GetArtData();
  const FS08AppliedRender& R = B.GetAppliedRender();
  TSharedRef<FJsonObject> Profiles = MakeShared<FJsonObject>();
  Profiles->SetNumberField(TEXT("revision"), Data.Revision);
  Profiles->SetStringField(TEXT("sha256"), Data.SourceSha256);
  Profiles->SetStringField(TEXT("source"), R.ProfilesSource);
  Root->SetObjectField(TEXT("profiles"), Profiles);
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetStringField(TEXT("profile"), B.GetArtProfileId());
  Board->SetStringField(TEXT("light"), R.ProfileId);
  Board->SetBoolField(TEXT("art"), B.IsArtActive());
  Board->SetBoolField(TEXT("mapImage"), B.IsMapImageActive());
  Board->SetNumberField(TEXT("buildCount"), B.GetBuildCount());
  Board->SetStringField(TEXT("fx"), B.GetFxOptions().Mode());
  Board->SetNumberField(TEXT("fighters"), B.GetFighters().Num());
  Root->SetObjectField(TEXT("board"), Board);
  const FS08EnvLayoutRuntime& Env = B.GetEnvLayoutRuntime();
  TSharedRef<FJsonObject> EnvObj = MakeShared<FJsonObject>();
  EnvObj->SetStringField(TEXT("status"), Env.Status.IsEmpty() ? TEXT("-") : Env.Status);
  EnvObj->SetStringField(TEXT("file"), FPaths::GetCleanFilename(Env.Layout.SourcePath));
  EnvObj->SetStringField(TEXT("sha256"), Env.Layout.SourceSha256);
  EnvObj->SetStringField(TEXT("variant"), Env.Variant.Name);
  EnvObj->SetStringField(TEXT("variantStatus"), Env.Variant.Status);
  EnvObj->SetStringField(TEXT("overlay"), FPaths::GetCleanFilename(Env.Layout.OverlayPath));
  EnvObj->SetStringField(TEXT("overlaySha256"), Env.Layout.OverlaySha256);
  EnvObj->SetNumberField(TEXT("props"), B.GetEnvProps().Num());
  EnvObj->SetNumberField(TEXT("fx"), Env.Fx.Num());
  Root->SetObjectField(TEXT("envLayout"), EnvObj);
  int32 EnvVisible = 0, ConceptVisible = 0;
  for (const UPointLightComponent* L : B.GetEnvLights()) EnvVisible += L && L->IsVisible() ? 1 : 0;
  for (const UPointLightComponent* L : B.GetConceptPasteLights()) ConceptVisible += L && L->IsVisible() ? 1 : 0;
  TSharedRef<FJsonObject> Lights = MakeShared<FJsonObject>();
  Lights->SetNumberField(TEXT("profileActors"), B.GetArtLightActorCount());
  Lights->SetNumberField(TEXT("envLights"), B.GetEnvLights().Num());
  Lights->SetNumberField(TEXT("envLightsVisible"), EnvVisible);
  Lights->SetNumberField(TEXT("conceptLights"), B.GetConceptPasteLights().Num());
  Lights->SetNumberField(TEXT("conceptLightsVisible"), ConceptVisible);
  Lights->SetNumberField(TEXT("heroLights"), B.GetHeroLightCount());
  Lights->SetNumberField(TEXT("heroLayersPerFigure"), B.GetHeroLightLayers());
  Lights->SetBoolField(TEXT("sky"), R.bSky);
  Lights->SetBoolField(TEXT("fog"), R.bFog);
  Lights->SetBoolField(TEXT("exposure"), R.bExposure);
  Lights->SetNumberField(TEXT("ev100"), R.Ev100);
  Root->SetObjectField(TEXT("lights"), Lights);
  const FS08HeroLightSpec* Hero = B.GetActiveHeroLight();
  TSharedRef<FJsonObject> HeroObj = MakeShared<FJsonObject>();
  HeroObj->SetBoolField(TEXT("on"), Hero != nullptr);
  HeroObj->SetStringField(TEXT("signature"), Hero ? Hero->Signature() : FString());
  Root->SetObjectField(TEXT("heroLight"), HeroObj);
  const FS08ConceptPasteMode& Mode = B.GetConceptPasteMode();
  TSharedRef<FJsonObject> Concept = MakeShared<FJsonObject>();
  Concept->SetBoolField(TEXT("on"), B.IsConceptPasteOn());
  Concept->SetStringField(TEXT("reason"), Mode.Reason);
  Concept->SetStringField(TEXT("kind"), S08ConceptKindName(Mode.Kind));
  Concept->SetStringField(TEXT("status"), B.GetConceptPasteRuntime().Status);
  Concept->SetNumberField(TEXT("parts"), B.GetConceptPasteParts().Num());
  Root->SetObjectField(TEXT("conceptPaste"), Concept);
  FString WhyNot;
  Root->SetBoolField(TEXT("renderReference"), S08RenderIsReference(R, WhyNot));
  Root->SetStringField(TEXT("renderWhyNot"), WhyNot);
  return Root;
}

void AS08FlowGameMode::LiveTuneWriteDone(FS08LiveResult& Result) {
  FS08LiveTuneSession& S = *LiveTune;
  Result.Ms = (FPlatformTime::Seconds() - S.CmdStartSeconds) * 1000.0;
  const FString Path = S08LiveTune::DoneFile(S.Dir, Result.Seq);
  const bool bWritten = S08LiveTune::WriteFileAtomic(Path, Result.ToJson());
  FS08Trace::Write(FString::Printf(TEXT("LIVETUNE done seq=%d action=%s ok=%d ms=%.0f errors=%d warnings=%d files=%d written=%d"),
                                   Result.Seq, *Result.Action, Result.bOk ? 1 : 0, Result.Ms, Result.Errors.Num(),
                                   Result.Warnings.Num(), Result.Files.Num(), bWritten ? 1 : 0));
  for (int32 I = 0; I < Result.Errors.Num() && I < 8; ++I) FS08Trace::Write(TEXT("LIVETUNE error: ") + Result.Errors[I]);
  S.LastCommandAt = Elapsed;
}

void AS08FlowGameMode::RunLiveTune() {
  if (!LiveTune.IsValid()) return;
  FS08LiveTuneSession& S = *LiveTune;
  switch (S.State) {
    case FS08LiveTuneSession::EState::Warming: {
      if (Elapsed < S.ReadyAt) return;
      S.State = FS08LiveTuneSession::EState::Idle;
      // clock calibration on this fresh start: the clip ran Elapsed - SpawnElapsed plus the spawn frame's dt (the game mode
      // ticks before the figures in a frame: the position read here is the previous frame's, hence + this frame's dt)
      if (BoardActor) {
        const float Dt = static_cast<float>(FApp::GetDeltaTime());
        for (const TPair<FString, float>& Start : S.ClipStart) {
          float Pos = 0.0f, Len = 0.0f;
          const AS08FighterActor* A = BoardActor->FindFighterActor(Start.Key);
          if (!A || !A->GetHeroClipTime(Pos, Len)) continue;
          const float Raw = (Pos - Start.Value) - (Elapsed - S.SpawnElapsed) + Dt;
          const float Offset = FS08LiveBenchClock::WrapClip(Raw + 0.5f * Len, Len) - 0.5f * Len;
          S.ClipOffset.Add(Start.Key, Offset);
          FS08Trace::Write(FString::Printf(TEXT("LIVETUNE clock calibration fighter=%s start=%.4f len=%.4f offset=%.4f"), *Start.Key,
                                           Start.Value, Len, Offset));
        }
      }
      TSharedPtr<FJsonObject> Ready = LiveTuneState();
      Ready->SetStringField(TEXT("state"), TEXT("ready"));
      Ready->SetNumberField(TEXT("warmup"), S.WarmupSeconds);
      Ready->SetStringField(TEXT("trace"), FS08Trace::IsJournalOn() ? TEXT("journal") : TEXT("-"));
      S08LiveTune::WriteFileAtomic(FPaths::Combine(S.Dir, S08LiveTuneSpec::ReadyFile), LiveJson(Ready.ToSharedRef()));
      FS08Trace::Write(FString::Printf(TEXT("LIVETUNE ready elapsed=%.1f dir=%s"), Elapsed, *S.Dir));
      S.LastCommandAt = Elapsed;
      return;
    }
    case FS08LiveTuneSession::EState::Shot:
      LiveTuneShotTick();
      return;
    case FS08LiveTuneSession::EState::Idle:
    default:
      break;
  }
  if (Elapsed < S.NextPollAt) return;
  S.NextPollAt = Elapsed + S08LiveTuneSpec::PollSeconds;
  int32 Seq = 0;
  FString Path;
  if (S08LiveTune::NextCommand(S.Dir, S.LastSeq, Seq, Path)) {
    LiveTuneHandleCommand(Path, Seq);
    return;
  }
  if (S.IdleExitSeconds > 0.0f && Elapsed - S.LastCommandAt > S.IdleExitSeconds) {
    // an orphaned session (the driver is gone) must not hold the GPU forever
    FS08Trace::Write(FString::Printf(TEXT("LIVETUNE idle exit after %.0f s without a command"), S.IdleExitSeconds));
    FS08Trace::Close();
    FGenericPlatformMisc::RequestExit(false);
    LiveTune.Reset();
  }
}

void AS08FlowGameMode::LiveTuneHandleCommand(const FString& Path, int32 Seq) {
  FS08LiveTuneSession& S = *LiveTune;
  S.LastSeq = Seq;
  S.CmdStartSeconds = FPlatformTime::Seconds();
  FS08LiveResult Result;
  Result.Seq = Seq;
  FString Text;
  TArray<FString> Errors;
  if (!FFileHelper::LoadFileToString(Text, *Path)) Errors.Add(FString::Printf(TEXT("cannot read %s"), *Path));
  FS08LiveCommand Cmd;
  if (Errors.IsEmpty()) FS08LiveCommand::Parse(Text, Seq, Cmd, Errors);
  Result.Action = S08LiveActionName(Cmd.Action);
  FS08Trace::Write(FString::Printf(TEXT("LIVETUNE command seq=%d action=%s parseErrors=%d"), Seq, *Result.Action, Errors.Num()));
  if (!Errors.IsEmpty()) {
    Result.Errors = Errors;
    LiveTuneWriteDone(Result);
    return;
  }
  S.Cmd = Cmd;
  switch (Cmd.Action) {
    case ES08LiveAction::Reload:
      LiveTuneReload(Cmd, Result);
      Result.bOk = Result.Errors.IsEmpty();
      LiveTuneWriteDone(Result);
      return;
    case ES08LiveAction::State:
      Result.Extra = MakeShared<FJsonObject>();
      Result.Extra->SetObjectField(TEXT("state"), LiveTuneState());
      Result.bOk = true;
      LiveTuneWriteDone(Result);
      return;
    case ES08LiveAction::Quit:
      Result.bOk = true;
      LiveTuneWriteDone(Result);
      FS08Trace::Write(TEXT("LIVETUNE quit"));
      FS08Trace::Close();
      FGenericPlatformMisc::RequestExit(false);
      LiveTune.Reset();
      return;
    case ES08LiveAction::Shot:
      LiveTuneStartShot();
      return;
    case ES08LiveAction::Tune:
    case ES08LiveAction::TunerState:
    case ES08LiveAction::TunerSave:
    case ES08LiveAction::TunerReset:
    case ES08LiveAction::TunerPanel:
      LiveTuneTuner(Cmd, Result);
      Result.bOk = Result.Errors.IsEmpty();
      LiveTuneWriteDone(Result);
      return;
    case ES08LiveAction::ArtView:
      LiveTuneArtView(Cmd, Result);
      Result.bOk = Result.Errors.IsEmpty();
      LiveTuneWriteDone(Result);
      return;
    default:
      Result.Errors.Add(TEXT("unknown action"));
      LiveTuneWriteDone(Result);
      return;
  }
}

void AS08FlowGameMode::LiveTuneReload(const FS08LiveCommand& Cmd, FS08LiveResult& Result) {
  FS08LiveTuneSession& S = *LiveTune;
  if (!BoardActor) {
    Result.Errors.Add(TEXT("no board actor"));
    return;
  }
  bool bOverride = false;
  FString Path = Cmd.ProfilesPath;
  if (Path.IsEmpty()) {
    Path = FS08BoardArtData::ResolvePath(bOverride);  // the startup source (the project file / pak, or -ArtBoardProfiles)
  } else {
    bOverride = !FPaths::IsSamePath(Path, FS08BoardArtData::DefaultPath());
  }
  // the journal from here on is the new build (its lines open the next shots' bench.trace.log)
  FS08Trace::TruncateJournal(0);
  FS08Trace::Write(FString::Printf(TEXT("LIVETUNE reload seq=%d profiles=%s source=%s envDir=%s"), Cmd.Seq, *Path,
                                   bOverride ? TEXT("override") : TEXT("pak"), Cmd.EnvDir.IsEmpty() ? TEXT("-") : *Cmd.EnvDir));
  TArray<FString> Errors, Warnings;
  if (!BoardActor->ReloadArtData(Path, bOverride, Cmd.EnvDir, Errors, Warnings)) {
    // invalid: nothing was touched, the board keeps the previous build (and the shots keep its trace lines)
    Result.Errors = Errors;
    Result.Warnings = Warnings;
    FS08Trace::TruncateJournal(0);
    return;
  }
  const int32 BuildsBefore = BoardActor->GetBuildCount();
  // nothing selected, as in the -Bench init (SyncBoardFromApplied would re-select the last shot's K2 hero)
  SelectFighter(FString());
  // the normal path of the first build: Rebuild (forced full) + team mapping + SyncFighters (+ hero light)
  SyncBoardFromApplied();
  SetupCameraForBoard();     // k1DistanceMul of the new profile; the camera a -Bench run starts with
  S.SpawnElapsed = Elapsed;  // the figures were spawned again by this rebuild
  ++S.Reloads;
  const int32 Builds = BoardActor->GetBuildCount();
  if (Builds != BuildsBefore + 1) Result.Errors.Add(TEXT("the forced Rebuild did not run"));
  const FS08BoardArtData& Data = BoardActor->GetArtData();
  FS08Trace::Write(FString::Printf(
      TEXT("LIVETUNE reload done seq=%d revision=%d sha256=%s source=%s buildCount=%d profile=%s art=%d fighters=%d heroLights=%d ms=%.0f"),
      Cmd.Seq, Data.Revision, *Data.SourceSha256, *BoardActor->GetAppliedRender().ProfilesSource, Builds,
      BoardActor->GetArtProfileId().IsEmpty() ? TEXT("-") : *BoardActor->GetArtProfileId(), BoardActor->IsArtActive() ? 1 : 0,
      BoardActor->GetFighters().Num(), BoardActor->GetHeroLightCount(), (FPlatformTime::Seconds() - S.CmdStartSeconds) * 1000.0));
  S.BuildLines = FS08Trace::JournalSlice(0, FS08Trace::JournalNum());
  FS08Trace::TruncateJournal(0);
  // Art Tuner: the panel continues on the reloaded document (its values written in again)
  ArtTunerProfilesPath = Path;
  if (ArtTuner.IsValid()) {
    ArtTunerRebase(Path, Warnings);
    ArtTunerApplyPending(true);
  }
  Result.Warnings = Warnings;
  Result.Extra = MakeShared<FJsonObject>();
  Result.Extra->SetNumberField(TEXT("revision"), Data.Revision);
  Result.Extra->SetStringField(TEXT("sha256"), Data.SourceSha256);
  Result.Extra->SetStringField(TEXT("source"), BoardActor->GetAppliedRender().ProfilesSource);
  Result.Extra->SetNumberField(TEXT("buildCount"), Builds);
  Result.Extra->SetStringField(TEXT("profile"), BoardActor->GetArtProfileId());
  Result.Extra->SetObjectField(TEXT("state"), LiveTuneState());
}

void AS08FlowGameMode::LiveTuneStartShot() {
  FS08LiveTuneSession& S = *LiveTune;
  const FS08LiveCommand& Cmd = S.Cmd;
  S.Files.Reset();
  S.Warnings.Reset();
  S.ViewInfos.Reset();
  S.View = 0;
  S.Settle = Cmd.Settle >= 0.0f ? Cmd.Settle : S.Clock.BenchSettle;
  S.Measure = Cmd.Measure >= 0.0f ? Cmd.Measure : 0.0f;
  S.Post = Cmd.Post >= 0.0f ? Cmd.Post : 0.0f;
  S.Warmup = Cmd.Warmup >= 0.0f ? Cmd.Warmup : 0.0f;
  S.SettleFrames = FMath::Max(Cmd.SettleFrames, 0);
  // the bench clock model of this shot (default: the session's -Bench values)
  S.ShotClock = S.Clock;
  FS08LiveBenchClock& Clock = S.ShotClock;
  if (Cmd.BenchWarmup >= 0.0f) Clock.BenchWarmup = Cmd.BenchWarmup;
  if (Cmd.BenchSettle >= 0.0f) Clock.BenchSettle = Cmd.BenchSettle;
  if (Cmd.BenchMeasure >= 0.0f) Clock.BenchMeasure = Cmd.BenchMeasure;
  if (Cmd.BenchGap > -1.5f) Clock.BenchGap = Cmd.BenchGap;
  if (Cmd.BenchGapLater > -1.5f) Clock.BenchGapLater = Cmd.BenchGapLater;
  IFileManager::Get().MakeDirectory(*Cmd.OutDir, true);
  S.TracePath = FPaths::Combine(Cmd.OutDir, S08LiveTuneSpec::TraceFile);
  if (!Cmd.bAppendTrace) IFileManager::Get().Delete(*S.TracePath, false, true, true);
  if (BoardActor && Cmd.bLive && BoardActor->GetFxOptions().bFreeze) {
    // live:true - Niagara / flicker / sway / water flow running for this shot: a full rebuild with the fx live, back to
    // the -Bench freeze after the shot (LiveTuneFinishShot)
    FS08EnvFxOptions Live = BoardActor->GetFxOptions();
    Live.bFreeze = false;
    BoardActor->SetFxOptionsOverride(Live);
    FS08Trace::TruncateJournal(0);
    SelectFighter(FString());
    BoardActor->RequestFullRebuild();
    SyncBoardFromApplied();
    S.SpawnElapsed = Elapsed;
    S.BuildLines = FS08Trace::JournalSlice(0, FS08Trace::JournalNum());
    S.bRestoreFx = true;
  }
  // the camera and selection a -Bench run starts its first view with
  SetupCameraForBoard();
  SelectFighter(FString());
  // the GPU caches of a fresh run for the first view (a K2 view of an earlier shot left sharper mips resident and hi-res
  // Lumen surface cache pages): the streamer keeps only the wanted mips until the first capture, Lumen re-captures
  S.bDropMipsActive = false;
  if (Cmd.bFresh) {
    S.PrevDropMips = LiveGetCvarInt(TEXT("r.Streaming.DropMips"), 0);
    S.bDropMipsActive = LiveSetCvar(TEXT("r.Streaming.DropMips"), TEXT("1"));
    const bool bLumenReset = LiveSetCvar(TEXT("r.LumenScene.SurfaceCache.Reset"), TEXT("1"));
    FS08Trace::Write(FString::Printf(TEXT("LIVETUNE fresh dropMips=%d (was %d, until the first capture) lumenSurfaceCacheReset=%d"),
                                     S.bDropMipsActive ? 1 : 0, S.PrevDropMips, bLumenReset ? 1 : 0));
  }
  FS08Trace::TruncateJournal(0);
  // bench.trace.log of this shot: the trace header and the lines of the current board build, then the shot itself
  FS08Trace::SetTee(S.TracePath);
  TArray<FString> Header;
  Header.Add(FS08Trace::Stamp(TEXT("--- S08 trace open ") + FDateTime::UtcNow().ToString() + TEXT(" ---")));
  for (const FString& Line : S.BootLines) {
    // a reload re-wrote the profile lines in the build lines (the boot ones would name the old document)
    if (S.Reloads > 0 && Line.Contains(TEXT("ARTPREVIEW board profiles "))) continue;
    Header.Add(Line);
  }
  Header.Append(S.BuildLines);
  FS08Trace::WriteTeeRaw(Header);
  const FString Views = FString::Join(Cmd.Views, TEXT("+"));
  FS08Trace::Write(FString::Printf(
      TEXT("LIVETUNE shot seq=%d tag=%s views=%s out=%s warmup=%.2f settle=%.2f settleFrames=%d measure=%.2f post=%.2f clock=%s bench=(warmup %.1f, settle %.1f, measure %.1f, gap %.3f/%.3f) fx=%s reloads=%d buildCount=%d"),
      Cmd.Seq, Cmd.Tag.IsEmpty() ? TEXT("-") : *Cmd.Tag, *Views, *Cmd.OutDir, S.Warmup, S.Settle, S.SettleFrames, S.Measure,
      S.Post, Cmd.bBenchClock ? TEXT("bench") : TEXT("free"), Clock.BenchWarmup, Clock.BenchSettle, Clock.BenchMeasure, Clock.BenchGap, Clock.BenchGapLater,
      BoardActor ? *BoardActor->GetFxOptions().Mode() : TEXT("-"), S.Reloads, BoardActor ? BoardActor->GetBuildCount() : 0));
  FS08Trace::Write(FString::Printf(
      TEXT("BENCH scene fixture=%s board=%dx%d fighters=%d viewer=%s hero=%s art=%d profile=%s views=%s warmup=%.0f settle=%.0f measure=%.0f fps=%.0f profileGpu=0 csv=0"),
      *FPaths::GetCleanFilename(S.Fixture), BoardModel.Width, BoardModel.Height, Fighters.Num(), *BenchViewerId,
      S.HeroId.IsEmpty() ? TEXT("-") : *S.HeroId, BoardActor && BoardActor->IsArtActive() ? 1 : 0,
      BoardActor && !BoardActor->GetArtProfileId().IsEmpty() ? *BoardActor->GetArtProfileId() : TEXT("-"), *Views,
      S.Warmup, S.Settle, S.Measure, S.BenchFps));
  S.Step = 1;
  S.NextAt = Elapsed + S.Warmup;
  S.NextFrame = GFrameCounter + static_cast<uint64>(FMath::Max(Cmd.WarmupFrames, 0));
  S.LastShotElapsed = Elapsed;
  S.ClockAtLastShot = 0.0f;
  S.State = FS08LiveTuneSession::EState::Shot;
}

void AS08FlowGameMode::LiveTuneSetClocks(float Target, const FString& View) {
  FS08LiveTuneSession& S = *LiveTune;
  // every looping clip to where a fresh -Bench run has it at this bench clock (the figures tick after the game mode in this
  // frame: the position set here gets this frame's dt added before it renders)
  const float Dt = static_cast<float>(FApp::GetDeltaTime());
  int32 Figures = 0, Set = 0;
  float HeroDelta = 0.0f;
  if (BoardActor) {
    for (const FS08BoardFighter& F : Fighters) {
      AS08FighterActor* A = BoardActor->FindFighterActor(F.Id);
      if (!A) continue;
      ++Figures;
      const float* Start = S.ClipStart.Find(F.Id);
      const float* Offset = S.ClipOffset.Find(F.Id);
      float Pos = 0.0f, Len = 0.0f;
      if (!Start || !Offset || !A->GetHeroClipTime(Pos, Len)) continue;
      const float Want = FS08LiveBenchClock::WrapClip(*Start + Target + *Offset - Dt, Len);
      const float Delta = FS08LiveBenchClock::WrapClip(Want - Pos, Len);
      if (A->ShiftHeroClipClock(Delta)) {
        ++Set;
        if (F.Id == S.HeroId) HeroDelta = Delta;
      }
    }
  }
  S.AnchorClock = Target;
  S.AnchorElapsed = Elapsed;
  // the material Time of a -Bench run (water / sea / mist / falls pan with the world time even in frozen runs)
  UWorld* World = GetWorld();
  const double Before = World ? World->TimeSeconds : 0.0;
  if (World) World->TimeSeconds = S.InitWorldTime + Target;
  FS08Trace::Write(FString::Printf(
      TEXT("LIVETUNE clock anchor view=%s benchClock=%.4f figures=%d clipsSet=%d heroShift=%.4f worldTime=%.4f->%.4f"),
      *View, Target, Figures, Set, HeroDelta, Before, World ? World->TimeSeconds : 0.0));
}

void AS08FlowGameMode::LiveTuneShotTick() {
  FS08LiveTuneSession& S = *LiveTune;
  const FS08LiveCommand& Cmd = S.Cmd;
  const FString View = Cmd.Views.IsValidIndex(S.View) ? Cmd.Views[S.View] : FString();
  auto Shoot = [&]() {
    if (S.Measure <= 0.0f) {
      FS08Trace::Write(S08RenderFingerprint(GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(),
                                            TEXT("BENCH")));
    }
    FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s shot-camera dist=%.1f target=%.1f exact=%d focus=%s"), *View,
                                     CameraZoom.Current, CameraZoom.Target,
                                     FMath::IsNearlyEqual(CameraZoom.Current, CameraZoom.Target, 0.05f) ? 1 : 0,
                                     *CameraZoom.CurrentFocus.ToCompactString()));
    TSharedRef<FJsonObject> Info = MakeShared<FJsonObject>();
    Info->SetStringField(TEXT("view"), View);
    if (Cmd.bBenchClock) {
      // the bench clock of this capture frame and the hero clip (read before the figures tick: the previous frame's)
      const float Clock = S.AnchorClock + (Elapsed - S.AnchorElapsed);
      float Pos = 0.0f, Len = 0.0f;
      const AS08FighterActor* Hero = BoardActor && !S.HeroId.IsEmpty() ? BoardActor->FindFighterActor(S.HeroId) : nullptr;
      const bool bClip = Hero && Hero->GetHeroClipTime(Pos, Len);
      const float* Start = S.ClipStart.Find(S.HeroId);
      const float* Offset = S.ClipOffset.Find(S.HeroId);
      const float Dt = static_cast<float>(FApp::GetDeltaTime());
      const float Want = bClip && Start && Offset ? FS08LiveBenchClock::WrapClip(*Start + Clock + *Offset - Dt, Len) : -1.0f;
      const float PoseErr = Want >= 0.0f ? FS08LiveBenchClock::WrapClip(Pos - Want + 0.5f * Len, Len) - 0.5f * Len : 0.0f;
      FS08Trace::Write(FString::Printf(
          TEXT("LIVETUNE clock shot view=%s target=%.4f clock=%.4f err=%.4f worldTime=%.4f hero=%s clip=%.4f/%.4f want=%.4f poseErr=%.4f"),
          *View, S.ShotClockTarget, Clock, Clock - S.ShotClockTarget, GetWorld() ? GetWorld()->TimeSeconds : 0.0,
          S.HeroId.IsEmpty() ? TEXT("-") : *S.HeroId, bClip ? Pos : -1.0f, bClip ? Len : -1.0f, Want, PoseErr));
      Info->SetNumberField(TEXT("clockTarget"), S.ShotClockTarget);
      Info->SetNumberField(TEXT("clockErr"), Clock - S.ShotClockTarget);
      Info->SetNumberField(TEXT("heroPoseErr"), PoseErr);
    }
    S.ClockAtLastShot = S.ShotClockTarget;
    S.LastShotElapsed = Elapsed;
    S.ShotPath = FPaths::Combine(Cmd.OutDir, S08LiveTune::ShotFileName(View));
    IFileManager::Get().Delete(*S.ShotPath, false, true, true);
    Info->SetStringField(TEXT("file"), S.ShotPath);
    Info->SetBoolField(TEXT("cameraExact"), FMath::IsNearlyEqual(CameraZoom.Current, CameraZoom.Target, 0.05f));
    S.ViewInfos.Add(MakeShared<FJsonValueObject>(Info));
    TakeEvidenceShot(S.ShotPath);
    if (S.bDropMipsActive) {
      // the first view is captured: the later views cache mips as a -Bench run does
      S.bDropMipsActive = false;
      LiveSetCvar(TEXT("r.Streaming.DropMips"), FString::FromInt(S.PrevDropMips));
    }
    S.NextAt = Elapsed + 15.0f;
    S.Step = 6;
  };
  switch (S.Step) {
    case 1:  // optional warm-up before the first view
      if (Elapsed < S.NextAt || GFrameCounter < S.NextFrame) return;
      FS08Trace::Write(FString::Printf(TEXT("BENCH warmup done elapsed=%.1f"), Elapsed));
      S.Step = 2;
      return;
    case 2:  // view setup: the -Bench camera of this view
      BenchSetupView(View, S.HeroId);
      S.StepStart = Elapsed;
      S.bSettleLogged = false;
      S.Step = 3;
      return;
    case 3: {  // camera settle, then the Lumen / TSR settle
      const bool bSettled = BenchCameraSettled();
      if (!bSettled && Elapsed - S.StepStart < 20.0f) return;
      if (!S.bSettleLogged) {
        S.bSettleLogged = true;
        FS08Trace::Write(FString::Printf(TEXT("BENCH view=%s camera settled=%d dist=%.1f target=%.1f zoom=%.2f"), *View,
                                         bSettled ? 1 : 0, CameraZoom.Current, CameraZoom.Target,
                                         CameraZoom.ZoomOf(CameraZoom.Current)));
        if (Cmd.bBenchClock) {
          const float LiveToShot = S.ShotClock.LiveAnchorToShot(S.Settle, S.Measure, S.Post);
          const float Target = S.ShotClock.AnchorClock(S.View, S.ClockAtLastShot, Elapsed - S.LastShotElapsed, LiveToShot);
          if (S.View > 0) {
            FS08Trace::Write(FString::Printf(TEXT("LIVETUNE clock gap view=%s live=%.4f model=%.4f"), *View,
                                             Elapsed - S.LastShotElapsed, S.ShotClock.GapBefore(S.View)));
          }
          LiveTuneSetClocks(Target, View);
          S.ShotClockTarget = Target + LiveToShot;
        }
        S.NextAt = Elapsed + S.Settle;
        S.NextFrame = GFrameCounter + static_cast<uint64>(S.SettleFrames);
      }
      if (Elapsed < S.NextAt || GFrameCounter < S.NextFrame) return;
      if (S.Measure > 0.0f) {
        S.FrameMs.Reset();
        S.GpuMs.Reset();
        S.GameMs.Reset();
        S.RenderMs.Reset();
        S.StepStart = Elapsed;
        S.Step = 4;
        return;
      }
      if (S.Post > 0.0f) {
        S.NextAt = Elapsed + S.Post;
        S.Step = 5;
        return;
      }
      Shoot();
      return;
    }
    case 4:  // measurement window (as -Bench; off by default)
      S.FrameMs.Add(static_cast<float>(FApp::GetDeltaTime() * 1000.0));
      S.GpuMs.Add(static_cast<float>(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles())));
      S.GameMs.Add(static_cast<float>(FPlatformTime::ToMilliseconds(GGameThreadTime)));
      S.RenderMs.Add(static_cast<float>(FPlatformTime::ToMilliseconds(GRenderThreadTime)));
      if (Elapsed - S.StepStart < S.Measure) return;
      FS08Trace::Write(FString::Printf(TEXT("BENCH measure view=%s window=%.1f %s"), *View, Elapsed - S.StepStart,
                                       *S08LiveTunePerfStats(S.FrameMs, S.GpuMs, S.GameMs, S.RenderMs)));
      FS08Trace::Write(S08RenderFingerprint(GetWorld(), BoardActor ? BoardActor->GetAppliedRender() : FS08AppliedRender(),
                                            TEXT("BENCH")));
      if (S.Post > 0.0f) {
        S.NextAt = Elapsed + S.Post;
        S.Step = 5;
        return;
      }
      Shoot();
      return;
    case 5:  // post wait (the -Bench ProfileGPU frame wait; 0 by default)
      if (Elapsed < S.NextAt) return;
      Shoot();
      return;
    case 6: {  // the PNG on disk, then the next view
      const bool bSaved = FPaths::FileExists(S.ShotPath);
      if (!bSaved && Elapsed < S.NextAt) return;
      FS08Trace::Write(FString::Printf(TEXT("BENCH shot view=%s saved=%d path=%s"), *View, bSaved ? 1 : 0, *S.ShotPath));
      if (bSaved) {
        S.Files.Add(S.ShotPath);
      } else {
        S.Warnings.Add(FString::Printf(TEXT("view %s: the capture was not saved within 15 s"), *View));
      }
      ++S.View;
      if (S.View < Cmd.Views.Num()) {
        S.Step = 2;
        return;
      }
      LiveTuneFinishShot(S.Files.Num() == Cmd.Views.Num(), FString());
      return;
    }
    default:
      LiveTuneFinishShot(false, TEXT("shot state machine lost"));
      return;
  }
}

void AS08FlowGameMode::LiveTuneFinishShot(bool bOk, const FString& Error) {
  FS08LiveTuneSession& S = *LiveTune;
  const FS08LiveCommand& Cmd = S.Cmd;
  FS08Trace::Write(FString::Printf(TEXT("BENCH done views=%d elapsed=%.1f"), Cmd.Views.Num(), Elapsed));
  FS08Trace::Write(FString::Printf(TEXT("LIVETUNE shot done seq=%d ok=%d files=%d ms=%.0f"), Cmd.Seq, bOk ? 1 : 0,
                                   S.Files.Num(), (FPlatformTime::Seconds() - S.CmdStartSeconds) * 1000.0));
  FS08Trace::ClearTee();
  FS08Trace::TruncateJournal(0);
  ++S.Shots;
  if (S.bDropMipsActive) {
    S.bDropMipsActive = false;
    LiveSetCvar(TEXT("r.Streaming.DropMips"), FString::FromInt(S.PrevDropMips));
  }
  if (S.bRestoreFx && BoardActor) {
    // back to the -Bench freeze (the build the next shots and reloads start from)
    S.bRestoreFx = false;
    BoardActor->SetFxOptionsOverride(TOptional<FS08EnvFxOptions>());
    SelectFighter(FString());
    BoardActor->RequestFullRebuild();
    SyncBoardFromApplied();
    SetupCameraForBoard();
    S.SpawnElapsed = Elapsed;
    S.BuildLines = FS08Trace::JournalSlice(0, FS08Trace::JournalNum());
    FS08Trace::TruncateJournal(0);
  }
  FS08LiveResult Result;
  Result.Seq = Cmd.Seq;
  Result.Action = S08LiveActionName(ES08LiveAction::Shot);
  Result.bOk = bOk && Error.IsEmpty();
  if (!Error.IsEmpty()) Result.Errors.Add(Error);
  if (!bOk && Error.IsEmpty()) Result.Errors.Add(TEXT("not every view was saved"));
  Result.Files = S.Files;
  if (FPaths::FileExists(S.TracePath)) Result.Files.Add(S.TracePath);
  Result.Warnings = S.Warnings;
  Result.Extra = MakeShared<FJsonObject>();
  Result.Extra->SetStringField(TEXT("out"), Cmd.OutDir);
  Result.Extra->SetStringField(TEXT("tag"), Cmd.Tag);
  Result.Extra->SetStringField(TEXT("clock"), Cmd.bBenchClock ? TEXT("bench") : TEXT("free"));
  Result.Extra->SetBoolField(TEXT("live"), Cmd.bLive);
  Result.Extra->SetBoolField(TEXT("fresh"), Cmd.bFresh);
  Result.Extra->SetNumberField(TEXT("settle"), S.Settle);
  Result.Extra->SetNumberField(TEXT("measure"), S.Measure);
  Result.Extra->SetNumberField(TEXT("post"), S.Post);
  Result.Extra->SetArrayField(TEXT("views"), S.ViewInfos);
  if (BoardActor) {
    Result.Extra->SetStringField(TEXT("profilesSha256"), BoardActor->GetArtData().SourceSha256);
    Result.Extra->SetNumberField(TEXT("revision"), BoardActor->GetArtData().Revision);
  }
  S.State = FS08LiveTuneSession::EState::Idle;
  LiveTuneWriteDone(Result);
}

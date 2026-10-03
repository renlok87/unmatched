// ENV-MAPS live tune (tools/art/render/LIVE-TUNE.md, AGENTS.md "Iteration speed"): parameter iterations in ONE running
// client instead of one engine launch per bench frame.
//
// -ArtLiveTune=<dir> (with the -Bench fixture flags, so the board, the figures and the camera are exactly the -Bench
// ones) turns the bench into a file-protocol server: the game thread polls <dir>/cmd-<seq>.json every 0.25 s and
// answers with <dir>/done-<seq>.json {seq, action, ok, ms, errors[], warnings[], files[], ...}. No socket, no network:
// files only. Without the flag nothing of this runs (no polling, no journal, the -Bench state machine unchanged).
//
// Actions (one at a time, in seq order):
//   reload  re-reads the board profiles (Config/ArtBoards/S08ArtBoardProfiles.json, or "profiles": <path>) and validates
//           every EnvLayouts/*.layout.json (or "envDir": <dir>) BEFORE touching the board: an invalid document is
//           reported in done.json and the board keeps its state. A valid one is swapped in and the board is rebuilt
//           through the normal path (AS08BoardActor::ReloadArtData + the game mode's SyncBoardFromApplied: Rebuild,
//           lights / fog / exposure / map grade, env layout, concept paste, backdrop, tray, fighters + hero light).
//   shot    {views, out, tag, settle, measure, post, live, clock}: per view the -Bench camera, settle, capture
//           bench-<View>-1920x1080.png + <out>/bench.trace.log in the -Bench trace format (the lines of the current
//           board build, BENCH view / RENDER / SHOT blocks), so the bench metric scripts read it unchanged.
//   state   the applied profile revision / sha, overlay sha, light counts, hero-light summary (done.json "state").
//   quit    answers, then exits.
// Art Tuner (S08ArtTuner.h, docs/art-pipeline/ART-TUNER-PLAN.md section 8) - the same code as the panel's sliders:
//   tune        {pointer, value} or {entries: [{pointer, value}]}: panel rows (registry pointers or row ids), validated by
//               the profile parser, applied at once (done.json: the scopes, the apply time, the values);
//   tunerState  the rows of this board with their values, the changed entries, the save file;
//   tunerSave   {file?}: writes S08ArtTuner.overrides.json (default -ArtTunerFile);
//   tunerReset  {group?}: one group (or everything) back to the profile file's values;
//   tunerPanel  {open}: shows / hides the panel (shots "with the panel");
//   artView     {view?, yaw?, pitch?, pan?: [x, y], select?, heroLight?, pause?, help?}: the -ArtView camera and keys.
#pragma once

#include "CoreMinimal.h"

class FJsonObject;

namespace S08LiveTuneSpec {
inline const TCHAR* const DirParam = TEXT("ArtLiveTune=");
/** Initial warm-up before ready.json (seconds; default = -BenchWarmup). */
inline const TCHAR* const WarmupParam = TEXT("ArtLiveTuneWarmup=");
/** The bench gap of the clock model (FS08LiveBenchClock::BenchGap; seconds, -1 = the live gap). */
inline const TCHAR* const BenchGapParam = TEXT("ArtLiveTuneBenchGap=");
inline const TCHAR* const BenchGapLaterParam = TEXT("ArtLiveTuneBenchGapLater=");
constexpr float PollSeconds = 0.25f;
constexpr int32 Protocol = 1;
inline const TCHAR* const ReadyFile = TEXT("ready.json");
inline const TCHAR* const TraceFile = TEXT("bench.trace.log");
/** The -Bench post-measure wait before a shot (ProfileGPU frame), RunRenderBench case 4 -> 5. */
constexpr float BenchPostSeconds = 3.0f;
inline const TCHAR* const ActionList =
    TEXT("reload | shot | state | quit | tune | tunerState | tunerSave | tunerReset | tunerPanel | artView");
}  // namespace S08LiveTuneSpec

enum class ES08LiveAction : uint8 {
  None, Reload, Shot, State, Quit, Tune, TunerState, TunerSave, TunerReset, TunerPanel, ArtView
};

UNMATCHED_API const TCHAR* S08LiveActionName(ES08LiveAction Action);

/** One parsed cmd-<seq>.json. Unset optional fields are < 0 / empty (the session fills the defaults). */
struct UNMATCHED_API FS08LiveCommand {
  int32 Seq = 0;
  ES08LiveAction Action = ES08LiveAction::None;
  // reload
  FString ProfilesPath;  // empty = FS08BoardArtData::ResolvePath (the startup source)
  FString EnvDir;        // empty = S08EnvLayout::ResolveDir
  // shot
  TArray<FString> Views;
  FString OutDir;
  FString Tag;
  float Warmup = -1.0f;   // extra wait before the first view (s)
  float Settle = -1.0f;   // per view after the camera settled (s); default the session's -BenchSettle
  float Measure = -1.0f;  // per view frame / GPU window (s); default 0
  float Post = -1.0f;     // per view wait before the capture (s); default 0
  int32 WarmupFrames = -1;  // the same waits in frames (both must pass when both are given)
  int32 SettleFrames = -1;
  bool bLive = false;       // Niagara / flicker / sway live for this shot (default: the -Bench freeze)
  /** The first view starts from a fresh run's GPU caches: the texture / mesh streamer drops its cached mips (a K2 view
   *  leaves sharper map mips resident that a fresh -Bench K1 never had) and Lumen re-captures its surface cache. */
  bool bFresh = true;
  bool bBenchClock = true;  // anim + world clocks of a fresh -Bench run at each capture ("clock":"free" = off)
  bool bAppendTrace = false;
  // bench clock model (default: the session's -BenchWarmup / -BenchSettle / -BenchMeasure)
  float BenchWarmup = -1.0f;
  float BenchSettle = -1.0f;
  float BenchMeasure = -1.0f;
  float BenchGap = -2.0f;       // < -1.5 = unset; -1 = the live gap; >= 0 = the first capture -> next anchor time
  float BenchGapLater = -2.0f;  // the same after the second and later captures
  // Art Tuner: tune (pointer -> value, in order), tunerSave (file), tunerReset (group), tunerPanel (open)
  TArray<TPair<FString, TSharedPtr<class FJsonValue>>> TuneEntries;
  FString TunerFile;
  FString TunerGroup;
  bool bPanelOpen = false;
  // artView: unset = keep (NaN / empty / -1)
  FString ArtViewView;
  float ArtViewYaw = NAN;
  float ArtViewPitch = NAN;
  bool bArtViewPan = false;
  FVector2D ArtViewPan = FVector2D::ZeroVector;
  bool bArtViewSelect = false;
  FString ArtViewSelect;
  int32 ArtViewHeroLight = -1;  // -1 keep, 0 off, 1 on
  int32 ArtViewPause = -1;
  int32 ArtViewHelp = -1;

  /** Parses Text; FileSeq = the seq of the file name (a "seq" field must match it). */
  static bool Parse(const FString& Text, int32 FileSeq, FS08LiveCommand& Out, TArray<FString>& OutErrors);
};

/** One done-<seq>.json. */
struct UNMATCHED_API FS08LiveResult {
  int32 Seq = 0;
  FString Action;
  bool bOk = false;
  double Ms = 0.0;
  TArray<FString> Errors;
  TArray<FString> Warnings;
  TArray<FString> Files;
  /** Extra top-level fields (state, timings, clock, ...). */
  TSharedPtr<FJsonObject> Extra;
  FString ToJson() const;
};

/** The -Bench timeline a live-tune shot reproduces at every capture (anim time since the figures spawned and the world
 *  time since the bench init): RunRenderBench reaches the first view's camera-settled tick Warmup + ~2.5 frames after the
 *  init tick, and a view's capture Settle + Measure + 3 s after its settled tick. Pure arithmetic (tested). */
struct UNMATCHED_API FS08LiveBenchClock {
  float BenchWarmup = 60.0f;
  float BenchSettle = 6.0f;
  float BenchMeasure = 5.0f;
  /** A -Bench capture -> the next view's camera-settled tick (file wait, view setup, camera tween; the capture frame's
   *  readback + PNG stall is part of it). < 0: the gap the live session measures instead - that one varies with the
   *  live stall (0.1-0.4 s seen), so a fixed value calibrated against fresh -Bench frames keeps the K2 poses: 0.57 / 0.41 s
   *  = the K2 figure poses of editor -game -Bench runs on Sarpedon and Cobble (2026-10-02 sweep, LIVE-TUNE.md). */
  float BenchGap = 0.57f;
  /** The gap after the second and later captures (< 0: BenchGap). The first capture of a fresh process stalls longer. */
  float BenchGapLater = 0.41f;
  float FrameSeconds = 1.0f / 60.0f;
  /** The modelled gap before view ViewIndex (>= 1), < 0 = use the live one. */
  float GapBefore(int32 ViewIndex) const {
    return ViewIndex >= 2 && BenchGapLater >= 0.0f ? BenchGapLater : BenchGap;
  }
  /** Bench clock (s since the bench init tick) at the first view's camera-settled tick. */
  float FirstAnchor() const { return BenchWarmup + 2.5f * FrameSeconds; }
  /** Settled tick -> capture tick of one -Bench view (settle, measure, the 3 s post wait; ~0.5 frame per phase). */
  float BenchAnchorToShot() const {
    return BenchSettle + BenchMeasure + S08LiveTuneSpec::BenchPostSeconds + 1.5f * FrameSeconds;
  }
  /** The same for the live machine: Settle + Measure (when > 0) + Post. */
  float LiveAnchorToShot(float Settle, float Measure, float Post) const {
    const int32 Phases = 1 + (Measure > 0.0f ? 1 : 0) + (Post > 0.0f ? 1 : 0);
    return Settle + FMath::Max(Measure, 0.0f) + FMath::Max(Post, 0.0f) + 0.5f * Phases * FrameSeconds;
  }
  /** The bench clock to set at a live anchor so that the live capture lands on the bench capture's clock:
   *  view 0: FirstAnchor + BenchAnchorToShot - LiveAnchorToShot;
   *  view i: ClockAtPreviousShot + GapSincePreviousShot + BenchAnchorToShot - LiveAnchorToShot
   *  (the gap - file wait, view setup, camera tween - is the same machine in both). */
  float AnchorClock(int32 ViewIndex, float ClockAtPreviousShot, float GapSincePreviousShot, float LiveToShot) const {
    const float Gap = GapBefore(ViewIndex) >= 0.0f ? GapBefore(ViewIndex) : GapSincePreviousShot;
    const float Base = ViewIndex == 0 ? FirstAnchor() : ClockAtPreviousShot + Gap;
    return Base + BenchAnchorToShot() - LiveToShot;
  }
  /** Bench clock of view i's capture: ClockAtAnchor + LiveToShot (what the trace reports as the target). */
  static float WrapClip(float Position, float Length) {
    if (Length <= 0.0f) return 0.0f;
    float P = FMath::Fmod(Position, Length);
    if (P < 0.0f) P += Length;
    return P;
  }
};

/** The game mode's live-tune state (S08FlowGameModeLiveTune.cpp). */
struct UNMATCHED_API FS08LiveTuneSession {
  enum class EState : uint8 { Warming, Idle, Shot };
  FString Dir;
  EState State = EState::Warming;
  int32 LastSeq = 0;
  float NextPollAt = 0.0f;
  float ReadyAt = 0.0f;
  float LastCommandAt = 0.0f;
  float IdleExitSeconds = 1800.0f;
  float WarmupSeconds = 0.0f;
  FString Fixture;
  FString HeroId;
  float BenchFps = 60.0f;
  int32 Reloads = 0;
  int32 Shots = 0;
  // trace journal: the board actor's BeginPlay lines (BoardBootEnd = their end) and the lines of the current build (the
  // init build, then each reload); a shot's bench.trace.log starts with them
  int32 BoardBootEnd = -1;
  TArray<FString> BootLines;
  TArray<FString> BuildLines;
  // clocks (FS08LiveBenchClock): the bench clock = seconds since the -Bench init tick; a figure's looping clip there is at
  // ClipStart (its idle phase at spawn) + clock + ClipOffset, where ClipOffset is the spawn frame's dt (the clip ticks in
  // the frame it spawns in; that first frame is a long one at start-up, a short one after a reload), calibrated once on
  // the session's own fresh start (= a fresh -Bench run's) when it becomes ready
  float SpawnElapsed = 0.0f;
  double InitWorldTime = 0.0;
  TMap<FString, float> ClipStart;
  TMap<FString, float> ClipOffset;
  float AnchorClock = 0.0f;    // the bench clock set at the last anchor
  float AnchorElapsed = 0.0f;  // Elapsed at that anchor
  FS08LiveBenchClock Clock;      // the session's model (-Bench* / -ArtLiveTuneBenchGap=)
  FS08LiveBenchClock ShotClock;  // the current shot's (Clock + the command's "bench" overrides)
  // the command in progress
  FS08LiveCommand Cmd;
  double CmdStartSeconds = 0.0;
  // shot state machine (the -Bench steps 2-6 of RunRenderBench)
  int32 Step = 0;
  int32 View = 0;
  float NextAt = 0.0f;
  uint64 NextFrame = 0;
  float StepStart = 0.0f;
  bool bSettleLogged = false;
  float Settle = 6.0f, Measure = 0.0f, Post = 0.0f, Warmup = 0.0f;
  int32 SettleFrames = 0;
  FString ShotPath;
  FString TracePath;
  TArray<float> FrameMs, GpuMs, GameMs, RenderMs;
  float ShotClockTarget = 0.0f;
  float ClockAtLastShot = 0.0f;
  float LastShotElapsed = 0.0f;
  bool bRestoreFx = false;
  bool bDropMipsActive = false;  // r.Streaming.DropMips=1 until the first view's capture ("fresh")
  int32 PrevDropMips = 0;
  TArray<FString> Files;
  TArray<FString> Warnings;
  TArray<TSharedPtr<class FJsonValue>> ViewInfos;
};

/** The -Bench 'BENCH measure' stats text (S08FlowGameMode.cpp S08PerfStats). */
FString S08LiveTunePerfStats(const TArray<float>& FrameMs, const TArray<float>& GpuMs, const TArray<float>& GameMs,
                             const TArray<float>& RenderMs);

namespace S08LiveTune {
/** -ArtLiveTune=<dir> (absolute, '/' separators), empty when the flag is absent: everything else is off then. */
UNMATCHED_API FString DirFromCommandLine();
UNMATCHED_API bool Enabled();
UNMATCHED_API FString CommandFile(const FString& Dir, int32 Seq);
UNMATCHED_API FString DoneFile(const FString& Dir, int32 Seq);
/** The lowest cmd-<seq>.json with seq > LastSeq (false when none). */
UNMATCHED_API bool NextCommand(const FString& Dir, int32 LastSeq, int32& OutSeq, FString& OutPath);
/** cmd-<seq>.json / done-<seq>.json -> seq (INDEX_NONE for any other name). */
UNMATCHED_API int32 SeqOfFileName(const FString& FileName, const TCHAR* Prefix);
/** The -Bench capture name of a view: bench-<View, '.' -> 'p'>-1920x1080.png (shared with RunRenderBench). */
UNMATCHED_API FString ShotFileName(const FString& View);
/** Writes <Path>.tmp then moves it over Path (a reader never sees a half file). */
UNMATCHED_API bool WriteFileAtomic(const FString& Path, const FString& Text);
/** "K1+K2x1.6" -> {"K1", "K2x1.6"}; false (with errors) for an empty list or a name outside [A-Za-z0-9.x]. */
UNMATCHED_API bool ParseViews(const FString& Text, TArray<FString>& OutViews, TArray<FString>& OutErrors);
}  // namespace S08LiveTune

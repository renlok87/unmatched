// VS-6 F4 (visual chat; docs/game-design/visual/06-tasks/vfx.csv FX-34, FX-35, FX-36; 02-visual-design.md §2.6,
// §9.2 CUE-016 / CUE-017 / CUE-018; cue-table.json postprocess blocks; ВР-24, ВР-FX08, ВР-FX09, ВР-VS5-SC33-02): the
// scene post process of the outcome and of the connection - one unbound APostProcessVolume spawned by the game mode,
// priority above the board profile's exposure volume (100), driven by a world-free state (unit-tested):
//
//   FX-34 CUE-016  outcome grade: victory WhiteTemp 6500 -> 7100 (warm); defeat WhiteTemp 6500 -> 5700 (cold) and ColorSaturation
//                  x 0.8; both VignetteIntensity = the engine base 0.4 + 0.25 (the board profile sets no vignette: its
//                  volume holds the exposure only, and the paste's grade.devignette 0.4 undoes exactly the base -
//                  the +0.25 stays visible on the painted plate too). Weight 0 -> 1 in 500 ms ease-in-out (reduced
//                  motion <= 100 ms) from the frame of the hero's `CUE death stage=gone` (or the `RESULT screen` frame
//                  without a hero death); held until the match is left; ABORTED, a draw, an unknown verdict and
//                  -S08FxLegacy: none. The camera, bloom, grain and LUT are never touched; UMG is drawn after it.
//   FX-35 CUE-017  the link lost (the HB-14 chip turns `lost`: the live stream not ready after it was ready): the
//                  scene saturation -30 % in the frame (engine ColorSaturation 0.64, ВР-VS6-43) (weight 1 at once), held until CUE-018; a repeated loss is a
//                  duplicate (D5, no change); with the defeat grade x 0.8 x 0.64.
//   FX-36 CUE-018  the link back (the stream ready and no state recovery pending - the frame the RECONNECT overlay
//                  closes): the disconnect weight 1 -> 0 linear in 300 ms (ВР-FX09 / ВР-VS5-SC33-02: inside the 800 ms
//                  CUE-018 show; reduced motion 100 ms); no "flash" of return.
//
// The weights compose in one settings block (the engine lerps overridden values, it never multiplies them):
//   WhiteTemp = 6500 + (target - 6500) x wO;  Saturation = (1 - 0.2 x wO [defeat]) x (1 - 0.36 x wD);
//   Vignette = 0.4 + 0.25 x wO.   All three run in the tonemapper pass (no extra pass, ΔGPU ~ 0).
// Trace (ВР-FX19 "FX " service lines):
//   FX grade outcome=<victory|defeat> t=<ms> ms=<500|100> reduced=<0|1> src=<gone|result> fighter=<id|->
//   FX grade outcome=none t=<ms> reason=<draw|unknown|legacy>
//   FX desat on t=<ms> sat=0.64 grade=<none|victory|defeat>          FX desat duplicate t=<ms>
//   FX desat off t=<ms> ms=<300|100> recovered_seq=<R>
//   FX postprocess off t=<ms> reason=<match-left|legacy>
#pragma once

#include "CoreMinimal.h"
#include "Engine/PostProcessVolume.h"

enum class ES08Outcome : uint8 { None, Victory, Defeat };

namespace S08CuePostProcess {
inline constexpr float BaseWhiteTemp = 6500.0f;
// ВР-VS6-44 (by delegation): FPostProcessSettings::WhiteTemp is the white-balance REFERENCE - a lower value renders
// the frame cooler (the editor -Bench K1: 5900 gave R/B 1.07 -> 0.94, 7300 gave 1.20). The card's 5900 / 7300 meant
// "warm victory, cold defeat" (purpose of FX-34), so the deltas are mirrored: victory 6500 + 600, defeat 6500 - 800.
inline constexpr float VictoryWhiteTemp = 7100.0f;
inline constexpr float DefeatWhiteTemp = 5700.0f;
inline constexpr float DefeatSaturation = 0.8f;
inline constexpr float BaseVignette = 0.4f;      // FPostProcessSettings::VignetteIntensity default (the board sets none)
inline constexpr float VignetteAdd = 0.25f;
// cue-table CUE-017 postprocess.desaturation 0.3 is measured on the frame (HSV S of the K1 frame -30 %, FX-35); the
// engine's ColorSaturation acts before the tone curve, which gives back chroma: 0.7 measured -25 %, 0.64 -> -30 %
// (ВР-VS6-43, by delegation; editor -Bench K1 Marmoreal and Sarpedon)
inline constexpr float DisconnectSaturation = 0.64f;
inline constexpr int32 OutcomeBlendMs = 500;
inline constexpr int32 RestoreMs = 300;
inline constexpr int32 ReducedMaxMs = 100;
inline constexpr float Priority = 200.0f;        // above the board profile's exposure volume (100)

UNMATCHED_API const TCHAR* OutcomeName(ES08Outcome Outcome);
/** Smoothstep 0..1 (the keyframes' ease-in-out). */
UNMATCHED_API float EaseInOut(float X);
/** The outcome weight at NowMs: 0 before StartMs, ease-in-out to 1 over BlendMs (BlendMs <= 0: 1 from the start). */
UNMATCHED_API float OutcomeWeight(int64 NowMs, int64 StartMs, int32 BlendMs);
/** The disconnect weight while restoring: 1 at StartMs, linear to 0 over Ms. */
UNMATCHED_API float RestoreWeight(int64 NowMs, int64 StartMs, int32 Ms);

struct FSettings {
  float WhiteTemp = BaseWhiteTemp;
  float Saturation = 1.0f;
  float Vignette = BaseVignette;
  bool bActive = false;  // any weight > 0 (else the component is disabled - zero cost)
};
/** The composed block for the outcome weight wO and the disconnect weight wD (see the header). */
UNMATCHED_API FSettings Compose(ES08Outcome Outcome, float OutcomeW, float DisconnectW);
}  // namespace S08CuePostProcess

/** The world-free state of the scene post process (Unmatched.S08.CuePostProcess.*). */
struct UNMATCHED_API FS08CuePostProcessState {
  ES08Outcome Outcome = ES08Outcome::None;
  int64 OutcomeStartMs = -1;
  int32 OutcomeBlendMs = S08CuePostProcess::OutcomeBlendMs;
  bool bDisconnected = false;
  int64 RestoreStartMs = -1;  // >= 0 while the colour returns
  int32 RestoreMsLen = S08CuePostProcess::RestoreMs;
  float BenchOutcomeW = -1.0f;  // -BenchFx=outcome,<w> / desat,<w>: frozen weights (>= 0)
  float BenchDisconnectW = -1.0f;

  bool HasOutcome() const { return Outcome != ES08Outcome::None && OutcomeStartMs >= 0; }
  /** FX-34: the grade starts at TMs (false and no line when one already runs). */
  bool StartOutcome(ES08Outcome InOutcome, int64 TMs, bool bReduced, const TCHAR* Src, const FString& FighterId,
                    FString& OutLine);
  /** FX-35: the loss at TMs; a loss while disconnected is a duplicate (OutLine = the duplicate line, false). */
  bool Disconnect(int64 TMs, FString& OutLine);
  /** FX-36: the return at TMs (false when not disconnected). */
  bool Reconnect(int64 TMs, bool bReduced, int32 RecoveredSeq, FString& OutLine);
  float DisconnectWeight(int64 NowMs) const;
  float OutcomeWeightAt(int64 NowMs) const;
  S08CuePostProcess::FSettings Evaluate(int64 NowMs) const;
  void Reset() { *this = FS08CuePostProcessState(); }
};

/** One frame of the connection watch (the HB-14 chip's inputs). */
struct FS08NetWatchInput {
  bool bStarted = false;           // the match runs (ES08Stage::Started)
  bool bStreamReady = false;       // FS08FlowController::IsStreamReady
  bool bAwaitingRecovery = false;  // FS08FlowController::IsAwaitingStateRecovery
};
enum class ES08NetEvent : uint8 { None, Lost, Recovered };

/** CUE-017 / CUE-018 edges, consistent with the HB-14 chip (UmConnection::Resolve): lost = the stream not ready after
 *  it was ready in this match (the chip's X); recovered = the stream ready again with no state recovery pending (the
 *  RECONNECT overlay closes, the reconnected toast). Every snapshot APPLIED while lost is the recovered state (D4: the
 *  missed events land as the final state, nothing replays): the caller feeds the reconnect of its seq before the
 *  snapshot's cues; at the recovery the reconnect runs only when no snapshot did it during this loss. */
struct UNMATCHED_API FS08NetWatch {
  bool bSeenReady = false;
  bool bLost = false;
  bool bReconnectFed = false;  // a snapshot applied during this loss already ran the reconnect
  ES08NetEvent Tick(const FS08NetWatchInput& In);
  /** A snapshot is applied (bApply: the seq guard's Apply decision): true when it is the recovered state (lost). */
  bool OnApplied(bool bApply);
  void Reset() { *this = FS08NetWatch(); }
};

namespace S08CuePostProcess {
/** A new unbound APostProcessVolume in World (priority 200, the three overrides set, disabled until a weight is > 0) -
 *  the same kind of volume the board profile spawns for its exposure (ВР-VS6-41: a UPostProcessComponent registered on
 *  the game mode changed nothing in the frame - the game mode has no scene root; Engine's UPostProcessComponent is
 *  MinimalAPI and cannot be subclassed from a game module). The state lives beside it. */
UNMATCHED_API APostProcessVolume* CreateVolume(UWorld& World);
/** Writes the composed settings (enables / disables the volume). */
UNMATCHED_API void Apply(APostProcessVolume& Volume, const FSettings& Settings);
}  // namespace S08CuePostProcess

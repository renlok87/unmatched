// MS-T-16 (move-selection 04 §6.3; DE footage 01 F-02, SD-13/14/20/50): the CUE-007 move animation as pure,
// world-free functions - the speed / reduced-motion settings, the seq schedule with those settings, the per-fighter
// plan (world points of the path, start, step time) and the pose of a figure at any time of its plan:
//   * the root slides linearly along each edge, the same time per edge whatever its length, no stop at a vertex;
//   * hop z = hopHeight * sin(pi t) per edge - a parameter, 0 by default (D-DE-02 / F-02: no hop);
//   * travel lean 10 deg forward, in over 60 ms from the start; start turn <= 50 ms, turn at a vertex 120 ms on the
//     move; after the arrival back to Idle in 150 ms (lean -> 0, facing -> the half-field rule);
//   * ease on the first / last edge - a parameter, off by default (02 "review resolution" p. 1);
//   * PLACE: fade out at the old cell, fade in at the new one (half of place_ms each); reduced motion / speed "none"
//     snap every move at 0.
// AS08FighterActor plays a plan (PlayMove / TickMove / FinishMove); the game mode builds the plans from the cues of a
// seq (HandleCues) and skips them on input (any key or mouse button but Space and the wheel, MS-E-70 / MS-E-110).
// Traces: "MS-ANIM settings ...", "MS-ANIM play|skip|jump ..." (S08FlowGameMode), MS-CUE `speed=` / `reduced=`.
#pragma once

#include "CoreMinimal.h"
#include "S08FlowController.h"
#include "InputCoreTypes.h"

namespace S08Motion {
inline const TCHAR* const ReducedMotionFlag = TEXT("S08ReducedMotion");
inline const TCHAR* const AnimSpeedParam = TEXT("S08AnimSpeed=");
/** none 0, fast 0.5, normal 1, slow 1.5 (04 §6.3). */
UNMATCHED_API double SpeedMul(ES08AnimSpeed Speed);
/** none | fast | normal | slow (the MS-CUE `speed=` token, cue_contract SPEED_MUL). */
UNMATCHED_API const TCHAR* SpeedName(ES08AnimSpeed Speed);
/** Case-insensitive none / fast / normal / slow; false (Out unchanged) otherwise. */
UNMATCHED_API bool ParseSpeed(const FString& Text, ES08AnimSpeed& Out);
/** The saved settings with the command-line overrides (04 §6.3): -S08ReducedMotion or bReducedCVar force reduced
 *  motion on; -S08AnimSpeed=<name> replaces the speed (an unknown name keeps the saved one). */
UNMATCHED_API FS08MotionSettings Resolve(const FS08MotionSettings& Saved, const TCHAR* CommandLine, bool bReducedCVar);
/** The effective settings now: US08UserSettings (when it is the engine's GameUserSettings class), the CVar
 *  s08.ReducedMotion and FCommandLine (S08UserSettings.cpp). */
UNMATCHED_API FS08MotionSettings Current();
/** MS-E-70 / MS-E-110: a press of this key or mouse button skips the moves - every keyboard key and mouse button but
 *  Space and the wheel (they drive the camera, D-10); gamepad, touch and axes do not. */
UNMATCHED_API bool SkipsMove(const FKey& Key);
/** All keys for which SkipsMove holds (EKeys::GetAllKeys, built once). */
UNMATCHED_API const TArray<FKey>& MoveSkipKeys();
}  // namespace S08Motion

/** Presentation parameters of a move (04 §6.3; 01 F-02). Defaults = the accepted values. */
struct UNMATCHED_API FS08MoveAnimParams {
  double HopHeightRel = 0.0;   // hop height as a fraction of the figure height; 0 = no hop (D-DE-02); A/B 0.08
  double TravelLeanDeg = 10.0; // forward lean in the travel direction; 0 = off
  double LeanInMs = 60.0;      // lean in from the move start
  double StartTurnMs = 50.0;   // turn to the first edge (<= one edge)
  double TurnMs = 120.0;       // turn to the next edge at a vertex, on the move (<= one edge)
  double SettleMs = 150.0;     // back to Idle after the arrival: lean -> 0, facing -> the rest rule
  bool bEaseEnds = true;       // AN-21 (ВР-12): ease-in on the first edge and ease-out on the last (default on)
  double EaseMs = 80.0;        // AN-21: the ease window at x1 (ms); an edge of T ms gets E = min(EaseMs x T / 280, T / 2)
  /** Review overrides for the A/B sheet (DE-028): -S08MoveHop=<rel>, -S08MoveLean=<deg>, -S08MoveEase (a no-op alias
   *  of the now-default ease). Rollback: -S08MoveEaseLegacy = the linear ends before ВР-12. */
  static FS08MoveAnimParams FromCommandLine(const TCHAR* CommandLine);
};

/** One fighter's move of a seq: world points of its path and its slot of the seq schedule. */
struct UNMATCHED_API FS08MovePlan {
  FString FighterId;
  int32 Seq = 0;
  int32 Order = 0;
  int32 Of = 1;
  ES08MoveKind Kind = ES08MoveKind::Move;
  TArray<FVector> Points;      // world cell centres WITH the start; Place = [from, to]
  double StartMs = 0.0;        // from the seq start (the snapshot frame)
  double StepMs = 0.0;         // per edge (Place: the whole transfer); 0 when snapped
  int32 Steps = 1;
  bool bSnapped = false;       // reduced motion, speed none, or past the seq cap: jumps to the end at StartMs
  double StartRestYawDeg = 0.0;  // facing (world forward yaw) on the start cell - the half-field rule
  double EndRestYawDeg = 0.0;    // facing on the destination cell
  double DurationMs() const { return bSnapped ? 0.0 : StepMs * Steps; }
  /** The arrival (end of the travel) from the seq start: the cascade point of a damage cue (MS-E-48). */
  double ArriveMs() const { return StartMs + DurationMs(); }
  /** End of the whole presentation (Idle settle included) from the seq start. */
  double EndMs(const FS08MoveAnimParams& Params) const;
  FVector Destination() const { return Points.Num() > 0 ? Points.Last() : FVector::ZeroVector; }
};

/** Pose of a figure at one moment of its plan. */
struct UNMATCHED_API FS08MovePose {
  FVector Location = FVector::ZeroVector;  // actor location (hop included)
  double YawDeg = 0.0;                     // world forward yaw of the figure
  double LeanDeg = 0.0;                    // forward lean towards the facing
  double HopUU = 0.0;
  double Fade = 0.0;                       // Place: dissolve progress 0..1 (0 = fully visible)
  int32 Edge = -1;                         // edge being travelled (-1 before the start / after the arrival)
  bool bStarted = false;
  bool bArrived = false;
  bool bDone = false;
};

struct UNMATCHED_API FS08MoveAnim {
  /** The seq schedule with the settings: reduced motion / speed none - every move snapped at 0; else
   *  FS08MoveCueSchedule with the speed multiplier (the MS-CUE trace uses exactly this). */
  static TArray<FS08MoveCueTiming> Schedule(const TArray<FS08Cue>& Cues, const FS08MotionSettings& Motion,
                                            TArray<const FS08Cue*>& OutMovesInOrder,
                                            const FS08MoveCueParams& Params = FS08MoveCueParams());
  /** One plan per FighterMoved cue (OrderInSeq order); CellToWorld maps a board cell to its world centre. */
  static TArray<FS08MovePlan> BuildPlans(const TArray<FS08Cue>& Cues, const FS08MotionSettings& Motion,
                                         TFunctionRef<FVector(const FIntPoint&)> CellToWorld,
                                         const FS08MoveCueParams& Params = FS08MoveCueParams());
  /** Pose at SeqMs (ms from the seq start) for a figure FigureHeightUU tall (the hop height). */
  static FS08MovePose Sample(const FS08MovePlan& Plan, const FS08MoveAnimParams& Params, double SeqMs,
                             double FigureHeightUU);
  /** Facing of a figure standing on a cell (world forward yaw): the legacy half-field rule
   *  (S08HeroesV2::FigureYawDeg - a rig v2 figure's yaw, +90 from the legacy 0 / 180). */
  static double RestYawDeg(const FVector& CellWorld);
  /** World yaw of the From -> To direction (degrees, XY plane). */
  static double TravelYawDeg(const FVector& From, const FVector& To);
  /** Relative rotation of a figure mesh: yaw (+ MeshYawOffsetDeg: 0 for a rig v2 figure facing +X, -90 for a legacy
   *  mesh facing +Y), leaned LeanDeg forward towards the facing (the top moves along the facing). */
  static FQuat FigureRotation(double YawDeg, double LeanDeg, double MeshYawOffsetDeg);
  /** DE-021 A/B frames (-BenchMovePose): a two-edge approach [N2, N1, Dest] that ends on Dest - N1 the free neighbour
   *  of Dest whose last edge runs most sideways to the board camera (largest |dX| share: the lean and the hop read in
   *  profile), N2 the free neighbour of N1 (not Dest) that continues that line best. Empty when there is none. */
  static TArray<FIntPoint> ReviewPath(const FIntPoint& Dest, TFunctionRef<TArray<FIntPoint>(const FIntPoint&)> Neighbours,
                                      TFunctionRef<bool(const FIntPoint&)> IsFree,
                                      TFunctionRef<FVector(const FIntPoint&)> CellToWorld);
};

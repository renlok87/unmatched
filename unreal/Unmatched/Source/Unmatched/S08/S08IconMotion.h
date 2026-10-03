// HUD icon motion v3 (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md): the data contract
// Config/S08IconMotion.json (= docs/unreal/contracts/hud/icon-motion.json) and a pure evaluator
// pose = f(commands, t). This is a line-by-line port of
// art/imagegen/hud-icons-v3/_tools/icon_motion.py; the automation test
// Unmatched.S08.IconMotion.Golden replays the Python reference poses
// (icon-motion-golden.json) and must match within 1e-3.
//
// Model (same as the contract `rules`):
//   - an icon is a canvas of 32 x 32 u (wide plates 64 x 32 u) and layers; a layer is a texture (whole icon,
//     icon layer, or a flipbook "<base>#" with Frames frames), a pivot and a rest pose;
//   - track target 0 is the root ("all"), target i + 1 is layer i;
//   - key {T, V, bFromStart, Ease}: Ease shapes the segment to the next key; bFromStart = the value the
//     property had when the command started; equal T = instant jump (the last key with T <= t wins);
//   - layer pose = rest <- base (enter -> loop/idle -> exit) <- events (latest event owns its properties);
//   - screen: point p of a layer -> R_all(R_layer(p)), R(p) = pivot + rot(s * (p - pivot)) + t;
//   - reduced motion: an animation's `reduced` branch replaces duration and tracks.
#pragma once

#include "CoreMinimal.h"

enum class ES08IconProp : uint8 { Scale, ScaleX, ScaleY, Tx, Ty, Rotate, Opacity, Frame, Num };
constexpr int32 S08IconPropCount = static_cast<int32>(ES08IconProp::Num);

enum class ES08IconEase : uint8 { Linear, Constant, EaseInQuad, EaseOutQuad, EaseOutCubic, EaseInOutCubic };
enum class ES08IconAnimKind : uint8 { Enter, Loop, Exit, Event };

struct FS08IconKey {
  float T = 0.0f;
  float V = 0.0f;
  bool bFromStart = false;
  ES08IconEase Ease = ES08IconEase::Linear;
};

struct FS08IconTrack {
  int32 Target = 0;  // 0 = root, i + 1 = layer i
  ES08IconProp Prop = ES08IconProp::Scale;
  TArray<FS08IconKey> Keys;
  bool HasFromStart() const;
};

struct FS08IconBranch {
  float DurationMs = 0.0f;
  TArray<FS08IconTrack> Tracks;
};

struct FS08IconAnim {
  FName Name;
  ES08IconAnimKind Kind = ES08IconAnimKind::Event;
  bool bHold = false;
  float BeatMs = -1.0f;    // -1 = no beat (sound / haptic hook)
  float StaggerMs = 0.0f;  // cascade step the caller applies (hint ranks)
  FS08IconBranch Normal;
  FS08IconBranch Reduced;
  bool bHasReduced = false;
  TMap<int32, FVector2D> Pivots;  // target -> pivot (u) while this animation drives it
  const FS08IconBranch& Branch(bool bReduced) const { return bReduced && bHasReduced ? Reduced : Normal; }
};

struct FS08IconLayer {
  FName Id;
  FString Src;  // "<icon>", "<icon>_<layer>", or a flipbook "<icon>_<layer>#"
  int32 Frames = 0;
  bool bHasPivot = false;
  FVector2D PivotU = FVector2D::ZeroVector;
  float Rest[S08IconPropCount] = {1.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  bool bTintTeam = false;
};

struct FS08IconDemoStep {
  FName Op;  // appear / leave / <event> / wait / cycle
  float Value = 0.0f;
};

struct FS08IconMotionDef {
  FName Icon;
  FVector2D CanvasU = FVector2D(32.0, 32.0);
  TArray<FS08IconLayer> Layers;
  TMap<FName, FS08IconAnim> Anims;
  TArray<FS08IconDemoStep> Demo;

  int32 TargetCount() const { return Layers.Num() + 1; }
  const FS08IconAnim* FindAnim(FName Name) const { return Anims.Find(Name); }
  /** Pivot (u) of a target: an active animation's pivot, else the layer pivot, else the canvas centre. */
  FVector2D PivotOf(int32 Target, const TMap<int32, FVector2D>& Active) const;
};

struct FS08IconTargetPose {
  float V[S08IconPropCount] = {1.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  FVector2D PivotU = FVector2D::ZeroVector;
  float Get(ES08IconProp P) const { return V[static_cast<int32>(P)]; }
};

struct FS08IconPose {
  TArray<FS08IconTargetPose> Targets;  // [0] root, [i + 1] layer i
  bool bVisible = false;
};

namespace S08IconMotion {
/** Easing of a normalized segment position X (clamped to [0, 1]). Constant = 0 (hold). */
UNMATCHED_API float Ease(ES08IconEase Ease, float X);
/** Value of a key list at local time T; bFromStart keys take Start. */
UNMATCHED_API float EvalKeys(const TArray<FS08IconKey>& Keys, float T, float Start);
/** UI-ACC-005/006 reduced motion: CVar s08.ReducedMotion > 0, or the -S08ReducedMotion command-line flag.
 *  MS-T-16 (US08UserSettings) becomes the source of the CVar. */
UNMATCHED_API bool IsReducedMotion();
/** /Game/S08/UI/IconsV3/T_IV3_<src with '-' -> '_'>[_fNN]_<size>.T_IV3_... (tools/art/icons_v3_import.py). */
UNMATCHED_API FString TextureObjectPath(const FString& Src, int32 Frame, int32 SizePx);
/** Gallery / reference demo script: (t, command) pairs and the total length (icon_motion.demo_schedule). */
UNMATCHED_API void DemoSchedule(const FS08IconMotionDef& Def, bool bReduced, TArray<TPair<float, FName>>& Out,
                                float& OutTotalMs);
}  // namespace S08IconMotion

/** The parsed contract. Get() loads Config/S08IconMotion.json once. */
class UNMATCHED_API FS08IconMotionLibrary {
public:
  bool LoadFromString(const FString& Json, FString* OutError = nullptr);
  bool LoadFile(const FString& Path, FString* OutError = nullptr);
  static FString DefaultPath();
  static const FS08IconMotionLibrary& Get();
  /** Variants (resource-hp-full-enemy, marker-status-p1/-p2) resolve to their base icon. */
  const FS08IconMotionDef* Find(FName Icon) const;

  FString Revision;
  TArray<FName> Order;
  TMap<FName, FS08IconMotionDef> Icons;
  TMap<FName, FName> Variants;
  bool bLoaded = false;
  bool bLoadAttempted = false;  // Get() reads the file once, also when it failed
};

/** State of one icon: commands Play(name, t) and Pose(t). Pure: no clock, no UObject. */
class UNMATCHED_API FS08IconAnimator {
public:
  void Init(const FS08IconMotionDef* InDef, bool bInReduced);
  /** false if the icon has no such animation. */
  bool Play(FName Anim, float TMs);
  FS08IconPose Pose(float TMs) const;
  /** True while anything moves at TMs (enter/exit/loop or an active event) - the widget skips work otherwise. */
  bool IsMoving(float TMs) const;
  /** True while the contract's cycle loops at TMs (contract rules.budget: <= 3 cycling icons per frame). */
  bool IsCycling(float TMs) const;
  const FS08IconMotionDef* GetDef() const { return Def; }
  bool IsReduced() const { return bReduced; }

private:
  struct FPlay {
    const FS08IconAnim* Anim = nullptr;
    float T0 = 0.0f;
    int32 Seq = 0;  // command order: at equal T0 the later command wins
    float Dur = 0.0f;
    const FS08IconBranch* Branch = nullptr;
    TMap<uint32, float> Start;  // (target << 8 | prop) -> value at command start
  };
  static uint32 Key(int32 Target, ES08IconProp Prop) { return (uint32(Target) << 8) | uint32(Prop); }
  /** The base play in effect at TMs and its local time; false = idle. */
  bool BaseAt(float TMs, FPlay& OutPlay, float& OutLocal) const;

  const FS08IconMotionDef* Def = nullptr;
  bool bReduced = false;
  bool bHasBase = false;
  FPlay Base;
  TArray<FPlay> Events;
  bool bShown = false;
  bool bHasHiddenFrom = false;
  float HiddenFrom = 0.0f;
  int32 SeqCounter = 0;
};

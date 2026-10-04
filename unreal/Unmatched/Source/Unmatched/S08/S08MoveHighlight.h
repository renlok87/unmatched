// MS-T-08 (docs/game-design/move-selection 04 §4.5, §6.1; 03 §4.1-§4.2a): the move-selection plates.
//
// What the board shows while a fighter is picked or a maneuver draft is open is one description, FS08MoveDraftView:
// one record per board space with ONE state per channel (ring / outline / centre dot / glyph), chosen by the
// priorities of 03 §4.2a. S08MoveHighlight::BuildDraftView makes it from the draft (pure, automation-tested);
// US08MoveHighlightComponent (owned by AS08BoardActor) draws it with four instanced static meshes created once per
// board - PlateFill, PlateRing, PlateOutline, Glyphs, one instance per board space each - and a selection, a hover or
// a boost change only rewrites custom data and transforms of the instances that changed (MS-R-49: no actor and no
// component is spawned or destroyed). Every instance is the engine plane under M_UM_MovePlate
// (/Game/S08/MoveSelection, built by tools/art/move_selection/ue_move_plate_material.py): an unlit translucent
// material that draws the plate shapes from the per-instance custom data (layout S08MovePlateCpd) and the style
// parameters (S08MovePlateParam, from the profile "moveSelection" block - live tune changes the MIDs only).
//
// Until the user's art acceptance (MS-T-27) the plates are opt-in: -S08MovePlates. Without the flag the board keeps
// the old readability ring (AS08BoardActor::SetSelectedFighter), so the reference frames of other sessions do not
// change (05 §4). Path line, ghosts and badges come with MS-T-09 / MS-T-10; the candidate ring V-17 is drawn here;
// S09MoveDraftView::BuildInput fills its fighters in MS-S-06 (DE-017).
#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08MoveHighlight.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UStaticMesh;

/** Ring channel, by DESCENDING priority (03 §4.2a); Candidate (V-17) is the lowest. The value is custom data [0]. */
enum class ES08RingState : uint8 {
  None = 0,
  Conflict,      // V-09
  NeedBoost,     // V-04b
  Destination,   // V-04
  Sent,          // V-10
  EnemyBlock,    // V-07
  AllyPass,      // V-06 (drawn on hover only)
  ReachBase,     // V-01
  ReachBoost,    // V-02
  PendingMove,   // V-11
  PendingPlace,  // V-12
  Candidate,     // V-17 (DE-017): own fighter that may move, under the figure
  Count
};
/** Outline channel, by descending priority. */
enum class ES08OutlineState : uint8 { None = 0, Threat, LastTo, LastFrom, Count };
/** Glyph channel, by descending priority (Order / Step / Hint are screen badges of MS-T-10 / MS-T-22: the world glyph
 *  draws nothing for them). */
enum class ES08GlyphState : uint8 { None = 0, Invalid, Conflict, Order, Step, Hint, Count };
/** Custom data [5]: which colour the channel uses. */
enum class ES08PlateColor : uint8 { Plate = 0, TeamP1, TeamP2, Error };

namespace S08PlateFlags {
constexpr uint8 Hover = 1;
constexpr uint8 Sent = 2;
constexpr uint8 Pulse = 4;
constexpr uint8 Occupied = 8;   // a living fighter stands here: nothing of the plate at r <= occupiedClearUU
constexpr uint8 LeaderPip = 16; // a hero's leader pip (+Y): the plate is cut +-pipCutDeg around it
}  // namespace S08PlateFlags

/** One board space with its state per channel (04 §4.5). */
struct UNMATCHED_API FS08PlateView {
  int32 X = -1;
  int32 Y = -1;
  ES08RingState Ring = ES08RingState::None;
  ES08OutlineState Outline = ES08OutlineState::None;
  bool bPathDot = false;
  ES08GlyphState Glyph = ES08GlyphState::None;
  int32 Steps = 0;
  int32 Chip = 0;   // "+N" of a boost-tier space / "+k" of a NeedBoost destination
  int32 Order = 0;  // 1-based send order of the move ending here (0 = none)
  int32 Rank = 0;
  uint8 Flags = 0;  // S08PlateFlags
  ES08PlateColor OutlineColor = ES08PlateColor::Plate;
  /** Candidate ring: the figure scale (hero 1, sidekick S08TeamRingSpec::SidekickScale). */
  float FigureScale = 1.0f;
};

struct UNMATCHED_API FS08PathView {
  FString FighterId;
  int32 Order = 0;
  TArray<FIntPoint> Cells;  // with the start
  bool bConflict = false;
  bool bNeedBoost = false;
  bool bSent = false;
  bool bPreview = false;
};

struct UNMATCHED_API FS08GhostView {
  FString FighterId;
  int32 X = -1;
  int32 Y = -1;
  float Alpha = 0.0f;
  int32 Order = 0;
  FString Label;
};

struct UNMATCHED_API FS08MoveDraftView {
  TArray<FS08PlateView> Plates;  // only spaces with a state; one record per space
  TArray<FS08PathView> Paths;
  TArray<FS08GhostView> Ghosts;
  TArray<FString> FadedFighters;
  FIntPoint Hover = FIntPoint(-1, -1);
  uint32 Revision = 0;
  /** Where the view came from (trace): draft | inspect | pending | reach | none | bench. */
  FString Source = TEXT("none");

  const FS08PlateView* Find(int32 X, int32 Y) const;
  bool IsEmpty() const { return Plates.Num() == 0 && Paths.Num() == 0 && Ghosts.Num() == 0; }
};

/** Input of BuildDraftView: the draft as plain data (S09 FS09CommandUi::MoveDraftInput fills it). */
struct UNMATCHED_API FS08MoveDraftInput {
  enum class EMoveStatus : uint8 { Ok, NeedBoost, Conflict };
  struct FMove {
    FString FighterId;
    FIntPoint Start = FIntPoint(-1, -1);
    FIntPoint Dest = FIntPoint(-1, -1);
    int32 Order = 0;  // 0-based index in moves[]
    EMoveStatus Status = EMoveStatus::Ok;
    int32 RequiredBoost = 0;
    TArray<FIntPoint> Path;  // canonical, WITHOUT the start
  };
  FString ViewerId;
  /** The fighter whose plates (tiers) are shown; empty = none. */
  FString SelectedFighterId;
  FIntPoint SelectedStart = FIntPoint(-1, -1);
  TArray<FIntPoint> BaseTier;
  TArray<TPair<FIntPoint, int32>> BoostTier;  // space + chip "+N"
  /** Graph distance limit of the enemy / ally marks (V-06 / V-07): base + the best boost. */
  int32 MarkRange = 0;
  TArray<FMove> Moves;
  bool bSent = false;  // the maneuver command is in flight (MS-S-05)
  /** MS-S-12 pending MOVE / PLACE: the legal spaces of the head. */
  bool bPending = false;
  bool bPendingPlace = false;
  TSet<uint64> PendingCells;
  /** V-17 (DE-017): own fighters that may move in this maneuver. */
  TArray<FString> CandidateFighterIds;
  FIntPoint Hover = FIntPoint(-1, -1);
  /** The board draws leader pips (readability "leaderPip"): a hero's space gets S08PlateFlags::LeaderPip. */
  bool bLeaderPips = false;
  FString Source = TEXT("draft");
};

namespace S08MoveHighlight {
/** -S08MovePlates (until MS-T-27 makes the plates the default); SetEnabledOverrideForTest overrides the command line. */
UNMATCHED_API bool PlatesEnabled();
UNMATCHED_API void SetEnabledOverrideForTest(TOptional<bool> bEnabled);

/** Resolves the channels of every space by 03 §4.2a; deterministic (plates sorted by Y, X). */
UNMATCHED_API FS08MoveDraftView BuildDraftView(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                               const FS08MoveDraftInput& Input);
/** The compatibility view of the old SetSelectedFighter(Id, Reachable): every reachable space except the fighter's own
 *  is ReachBase (pending choices and the legacy quick move). */
UNMATCHED_API FS08MoveDraftView ViewFromReachable(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                                  const FString& FighterId, const TSet<uint64>& Reachable,
                                                  bool bLeaderPips);
/** Content signature of a view (the component skips an unchanged view; the trace names it). */
UNMATCHED_API uint32 ViewHash(const FS08MoveDraftView& View);
UNMATCHED_API const TCHAR* RingStateName(ES08RingState State);
UNMATCHED_API const TCHAR* OutlineStateName(ES08OutlineState State);
UNMATCHED_API const TCHAR* GlyphStateName(ES08GlyphState State);

/** 03 §4.1 geometry of a style, as the material draws it (MS-AT-21 'MS-HL geom'): the ring with its keyline, the
 *  outline, the occupied clear circle and the leader-pip cut against the pip footprint of S08LeaderPipTransforms. */
struct UNMATCHED_API FGeometryCheck {
  float RingBandInner = 0.0f, RingBandOuter = 0.0f;
  float OutlineInner = 0.0f, OutlineOuter = 0.0f;
  float OccupiedClear = 0.0f;
  float PipCutDeg = 0.0f;
  /** Half angle (deg) the pip (with its keyline) covers at the ring band, seen from the space centre. */
  float PipHalfAngleDeg = 0.0f;
  bool bRingInBand = false;      // [30, 40]
  bool bOutlineInBand = false;   // [39.6, 41.0] .. inside the rim 41.6
  bool bOccupiedClear = false;   // nothing at r <= 30 on an occupied space
  bool bPipClear = false;        // the cut covers the pip: the ring never crosses it
  bool Ok() const { return bRingInBand && bOutlineInBand && bOccupiedClear && bPipClear; }
  FString TraceLine(const FString& Source) const;
};
UNMATCHED_API FGeometryCheck CheckGeometry(const FS08MoveSelectionSpec& Spec);
}  // namespace S08MoveHighlight

/** Material contract of M_UM_MovePlate (tools/art/move_selection/ue_move_plate_material.py builds it from these names;
 *  its --check compares them with this header). */
namespace S08MovePlateSpec {
inline const TCHAR* const MaterialPath = TEXT("/Game/S08/MoveSelection/M_UM_MovePlate.M_UM_MovePlate");
/** Half size of a plate instance (uu): the engine plane (100 uu) at scale 2 x HalfUU / 100 covers the outline (41)
 *  and the square of a grid cell (41) with a margin. */
constexpr float HalfUU = 44.0f;
constexpr int32 NumCustomData = 6;
/** Channel of an ISM ("Channel" parameter of its MID). */
enum class EChannel : uint8 { Fill = 0, Ring = 1, Outline = 2, Glyph = 3, Count = 4 };
UNMATCHED_API const TCHAR* ChannelName(EChannel Channel);
/** Height of a channel above the play plane (03 §4.1): fill zFill, ring / outline zRing, glyph 2.0. */
constexpr float GlyphZ = 2.0f;
/** Scalar parameters. */
inline const TCHAR* const ParamChannel = TEXT("Channel");
inline const TCHAR* const ParamShape = TEXT("Shape");          // 0 = circle (map space), 1 = rounded square (grid)
inline const TCHAR* const ParamHalfUU = TEXT("HalfUU");
inline const TCHAR* const ParamRingCenter = TEXT("RingCenter");
inline const TCHAR* const ParamRingWidth = TEXT("RingWidth");
inline const TCHAR* const ParamKeyline = TEXT("Keyline");
inline const TCHAR* const ParamOutlineInner = TEXT("OutlineInner");
inline const TCHAR* const ParamOutlineOuter = TEXT("OutlineOuter");
inline const TCHAR* const ParamOccClear = TEXT("OccClear");
inline const TCHAR* const ParamPipCutDeg = TEXT("PipCutDeg");
inline const TCHAR* const ParamFillAlpha = TEXT("FillAlpha");
inline const TCHAR* const ParamDashCount = TEXT("DashCount");
inline const TCHAR* const ParamDashDuty = TEXT("DashDuty");
inline const TCHAR* const ParamCandRadius = TEXT("CandRadius");
inline const TCHAR* const ParamCandWidth = TEXT("CandWidth");
inline const TCHAR* const ParamCandAlpha = TEXT("CandAlpha");
inline const TCHAR* const ParamLastMoveAlpha = TEXT("LastMoveAlpha");
/** Vector parameters (linear = FLinearColor::FromSRGBColor of the profile hex). */
inline const TCHAR* const ParamPlateColor = TEXT("PlateColor");
inline const TCHAR* const ParamKeylineColor = TEXT("KeylineColor");
inline const TCHAR* const ParamErrorColor = TEXT("ErrorColor");
inline const TCHAR* const ParamTeamP1Color = TEXT("TeamP1Color");
inline const TCHAR* const ParamTeamP2Color = TEXT("TeamP2Color");
/** Screen team colours of the outline (03 §4.2 V-14/V-15: #DAC576 / #5786A8). */
inline const FColor TeamP1Screen = FColor(0xDA, 0xC5, 0x76, 255);
inline const FColor TeamP2Screen = FColor(0x57, 0x86, 0xA8, 255);
}  // namespace S08MovePlateSpec

/** Custom data slots of every plate instance (04 §6.1). */
namespace S08MovePlateCpd {
constexpr int32 State = 0;       // channel state (ES08RingState / ES08OutlineState / ES08GlyphState)
constexpr int32 Steps = 1;       // steps / 10; a Candidate ring: the figure scale
constexpr int32 Chip = 2;        // +N / +k
constexpr int32 GlyphIndex = 3;  // atlas index (MS-T-10; 0 now)
constexpr int32 Flags = 4;       // S08PlateFlags
constexpr int32 Color = 5;       // ES08PlateColor
}  // namespace S08MovePlateCpd

UCLASS()
class UNMATCHED_API US08MoveHighlightComponent : public USceneComponent {
  GENERATED_BODY()

public:
  US08MoveHighlightComponent();

  /** Creates the four ISMs (once) on Plane and loads M_UM_MovePlate; traces 'MS-HL assets'. A missing material leaves
   *  the component unready (IsReady false): the board then keeps the old readability ring. */
  void Initialize(UStaticMesh* Plane);
  bool IsReady() const { return bReady; }
  /** One hidden instance per board space on every channel (a full board rebuild / live-tune reload); applies the style
   *  to the MIDs and traces 'MS-HL build' and 'MS-HL geom'. */
  void BuildForBoard(const FS08BoardModel& Board, const FS08MoveSelectionSpec& Style);
  /** The style only (live tune: MID parameters, no instance touched). */
  void ApplyStyle(const FS08MoveSelectionSpec& Style);
  /** Writes the channels of every space from View; only the instances whose data changed are touched. Returns the
   *  number of instance updates (0 for an unchanged view). */
  int32 ApplyView(const FS08MoveDraftView& View);
  void ClearView() { ApplyView(FS08MoveDraftView()); }

  // ---- inspection (automation, traces) ----
  int32 GetSpaceCount() const { return SpaceCells.Num(); }
  const UInstancedStaticMeshComponent* GetChannel(S08MovePlateSpec::EChannel Channel) const;
  /** Instance index of a space (INDEX_NONE off the board / not a space). */
  int32 InstanceOf(int32 X, int32 Y) const;
  /** Custom data value of a channel instance (0 when absent). */
  float GetCustomData(S08MovePlateSpec::EChannel Channel, int32 Instance, int32 Slot) const;
  /** True when the channel instance is drawn (non-zero scale). */
  bool IsInstanceVisible(S08MovePlateSpec::EChannel Channel, int32 Instance) const;
  const FS08MoveSelectionSpec& GetStyle() const { return Style; }
  const FString& GetMaterialName() const { return MaterialName; }
  int32 GetBuildCount() const { return BuildCount; }
  uint32 GetAppliedHash() const { return AppliedHash; }
  /** Test-only: draw without the material (a test world loads it like a game; a missing asset is reported, not drawn). */
  void SetReadyForTest() { bReady = true; }

private:
  void EnsureChannels();
  void WriteInstance(S08MovePlateSpec::EChannel Channel, int32 Instance, const float (&Data)[S08MovePlateSpec::NumCustomData],
                     bool bShow, float Z);

  UPROPERTY()
  TArray<TObjectPtr<UInstancedStaticMeshComponent>> Channels;
  UPROPERTY()
  TArray<TObjectPtr<UMaterialInstanceDynamic>> ChannelMids;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> PlateMaterial;
  UPROPERTY()
  TObjectPtr<UStaticMesh> PlaneMesh;
  bool bReady = false;
  bool bInitialized = false;
  FString MaterialName;
  FS08MoveSelectionSpec Style;
  bool bSquare = false;
  FS08BoardModel Board;
  TArray<FIntPoint> SpaceCells;          // instance index -> space
  TMap<uint64, int32> InstanceByCell;    // FS08BoardModel::CellKey -> instance index
  /** Last written data / visibility / z per channel instance (an unchanged instance is not touched). */
  TArray<TArray<TArray<float>>> Written;  // [channel][instance][slot]
  TArray<TArray<float>> WrittenZ;         // [channel][instance], < -1e5 = hidden
  uint32 AppliedHash = 0;
  int32 BuildCount = 0;
};

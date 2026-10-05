// MS-T-08: the bridge from the maneuver draft (FS09CommandUi, S09ManeuverUi.h) to the plate view of the board
// (FS08MoveDraftView, S08/S08MoveHighlight.h), and the -BenchMoveDraft scene fixtures (04 §6.4, 06 §6.2).
//
// -BenchMoveDraft=<abs path> lays a draft over the -BenchFixture game state (board, fighters, hand): the client
// synthesises metadata.pendingManeuver {id "bench:<file name>", playerId benchViewerId}, opens the draft through the
// same FS09CommandUi.OnSnapshot as a live snapshot and replays the file's operations (boost card, moves in order,
// order changes, selection) with the real draft functions - no server. A fighter or card id the bench fixture does
// not have is a 'MS-BENCH mismatch id=<id>' and no frame is taken. Format unmatched.move-draft/1
// (tools/s08/fixtures/move-draft/<board>-<scene>.json, outside Config/: never in the pak):
//   { "schema": "unmatched.move-draft/1", "board": "<profile id>", "benchFixture": "S08Bench<Map>.json",
//     "scene": "<name>", "selected": "<fighter id>", "hover": "<space id>" | [x, y],
//     "boostCardId": "<own hand instance id>", "moves": [{"fighterId": "<id>", "to": "<space id>" | [x, y]}],
//     "moveOrder": [{"fighterId": "<id>", "delta": -1 | 1}],
//     "lastMovement": {...},                          <- reserved for MS-T-17 (traced as skipped)
//     "pending": {"type": "MOVE" | "PLACE", "fighterId": "<id>", "value": <n>, "optional": <bool>,
//                 "targetsOpponent": <bool>, "to": "<space id>" | [x, y]} }
// MS-T-12: "pending" synthesises metadata.pendingEffects [{id "bench-pending:<file name>", playerId benchViewerId,
// type, value (omitted = absent), optional, fighterIds [fighterId], targetsOpponent}] INSTEAD of the pendingManeuver -
// the MS-S-12 plates V-11 / V-12 (and V-04 + path with "to"); it excludes boostCardId / moves / moveOrder / selected.
#pragma once

#include "CoreMinimal.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08MoveHighlight.h"
#include "S09ManeuverUi.h"

namespace S09MoveDraftView {
/** The plate input of the current draft: the selected fighter's tiers (MS-S-06/07, also the MS-S-02 inspection), every
 *  drafted move with its status and path, the pre-draft target (MS-S-03), the in-flight flag (MS-S-05) and a pending
 *  MOVE / PLACE head of the viewer (MS-S-12) and the candidate rings V-17 of MS-S-06 (DE-017: every own fighter that
 *  may move while none is selected and the draft is not sent). Hover and leader pips are the caller's. */
UNMATCHED_API FS08MoveDraftInput BuildInput(const FS09CommandUi& Ui, const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters);
}  // namespace S09MoveDraftView

namespace S09MoveDraftBench {
struct UNMATCHED_API FCellRef {
  FString SpaceId;  // "M13" on an original map
  FIntPoint Cell = FIntPoint(-1, -1);
  bool bSet = false;
  /** The space on Board (SpaceId first, else the lattice cell); false when it is not a board space. */
  bool Resolve(const FS08BoardModel& Board, FIntPoint& Out) const;
  FString Describe() const;
};

struct UNMATCHED_API FFixture {
  FString File;
  FString Board;
  FString BenchFixture;
  FString Scene;
  FString Selected;
  FCellRef Hover;
  FString BoostCardId;
  struct FMove {
    FString FighterId;
    FCellRef To;
  };
  TArray<FMove> Moves;
  struct FOrder {
    FString FighterId;
    int32 Delta = 0;
  };
  TArray<FOrder> MoveOrder;
  /** MS-T-12: a pending MOVE / PLACE head of the viewer (MS-S-12) instead of a maneuver draft. */
  struct FPending {
    bool bSet = false;
    FString Type;
    FString FighterId;
    int32 Value = -1;  // < 0: the field is absent (server `value ?? 1`)
    bool bOptional = false;
    bool bTargetsOpponent = false;
    FCellRef To;
  };
  FPending Pending;
  /** Reserved fields present in the file (lastMovement): traced, not applied. */
  TArray<FString> Skipped;
};

/** Parses an unmatched.move-draft/1 document (structure only; ids are checked by Apply). */
UNMATCHED_API bool Parse(const FString& Text, const FString& FileName, FFixture& Out, TArray<FString>& OutErrors);

struct UNMATCHED_API FApplyResult {
  bool bOk = false;
  FString MismatchId;  // a fighter / card id the bench fixture does not have
  FString Error;
  FIntPoint Hover = FIntPoint(-1, -1);
  FS08Snapshot Snapshot;  // the bench snapshot with the synthesised pendingManeuver
  /** 'MS-BENCH draft ...' summary line. */
  FString Summary;
};

/** Opens the draft on Ui from Snapshot (+ the synthesised pendingManeuver of ViewerId) and replays the fixture. */
UNMATCHED_API FApplyResult Apply(const FFixture& Fixture, const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                 const TArray<FS08BoardFighter>& Fighters, const FString& ViewerId, FS09CommandUi& Ui);
}  // namespace S09MoveDraftBench

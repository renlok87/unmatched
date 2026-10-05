// MS-T-08: the move plates of the game mode (docs/game-design/move-selection 04 §6.1, §6.4) - the board's view provider
// (the CommandUi draft as plates), the tick that re-draws them after a draft operation, and the -BenchMoveDraft scene.
#include "S08FlowGameMode.h"

#include "S08BoardActor.h"
#include "S08MoveHighlight.h"
#include "S08TraceLog.h"
#include "../S09/S09MoveDraftView.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

bool AS08FlowGameMode::BuildMoveDraftViewFor(const FString& FighterId, const TSet<uint64>& Reachable,
                                             FS08MoveDraftView& OutView) {
  (void)Reachable;
  const bool bDraft = CommandUi.Mode == ES09CommandMode::ManeuverDraft;
  // MS-S-02 / MS-S-03: the inspection of an own fighter and the pre-draft target before the draw
  const bool bInspect = CommandUi.Mode == ES09CommandMode::None &&
                        ((!CommandUi.SelectedFighterId.IsEmpty() && FighterId == CommandUi.SelectedFighterId) ||
                         CommandUi.PreDraft.bSet);
  // MS-S-12: a pending MOVE / PLACE head of this viewer (V-11 / V-12)
  const bool bPending = CommandUi.Mode == ES09CommandMode::PendingChoice && CommandUi.bHasPendingChoice &&
                        (CommandUi.PendingChoice.Type == TEXT("MOVE") || CommandUi.PendingChoice.Type == TEXT("PLACE"));
  if (!bDraft && !bInspect && !bPending) return false;
  FS08MoveDraftInput Input = S09MoveDraftView::BuildInput(CommandUi, BoardModel, Fighters);
  Input.Hover = MoveHoverCell;
  Input.bLeaderPips = BoardActor && BoardActor->DrawsLeaderPips();
  if (bBenchMoveDraft) Input.Source = TEXT("bench");
  OutView = S08MoveHighlight::BuildDraftView(BoardModel, Fighters, Input);
  return true;
}

void AS08FlowGameMode::SyncMovePlates() {
  if (!BoardActor || !BoardActor->UsesMovePlates()) return;
  // what the view depends on besides the selection (whose change already calls SetSelectedFighter)
  uint32 Key = HashCombineFast(GetTypeHash(CommandUi.DraftRevision), static_cast<uint32>(CommandUi.Mode));
  Key = HashCombineFast(Key, (CommandUi.bCommandInFlight ? 1u : 0u) | (CommandUi.PreDraft.bSet ? 2u : 0u) |
                                 (CommandUi.bHasPendingChoice ? 4u : 0u));
  Key = HashCombineFast(Key, GetTypeHash(FIntPoint(CommandUi.PreDraft.X, CommandUi.PreDraft.Y)));
  Key = HashCombineFast(Key, GetTypeHash(CommandUi.PreDraft.FighterId));
  Key = HashCombineFast(Key, GetTypeHash(CommandUi.SelectedFighterId));
  Key = HashCombineFast(Key, GetTypeHash(CommandUi.PendingCells.Num()));
  // MS-T-12: the pending fighter and target (V-04 + path of a picked MOVE / PLACE target)
  Key = HashCombineFast(Key, GetTypeHash(CommandUi.PendingFighterId));
  Key = HashCombineFast(Key, GetTypeHash(CommandUi.bPendingCellSet ? FIntPoint(CommandUi.PendingCellX, CommandUi.PendingCellY)
                                                                   : FIntPoint(-1, -1)));
  Key = HashCombineFast(Key, GetTypeHash(MoveHoverCell));
  if (Key == MovePlatesKey) return;
  MovePlatesKey = Key;
  BoardActor->RefreshMoveDraftView();
}

bool AS08FlowGameMode::ApplyBenchMoveDraft(const FS08Snapshot& Snapshot, const FString& Path, FString& OutError) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) {
    OutError = FString::Printf(TEXT("cannot read %s"), *Path);
    return false;
  }
  S09MoveDraftBench::FFixture Fixture;
  TArray<FString> Errors;
  if (!S09MoveDraftBench::Parse(Text, FPaths::GetCleanFilename(Path), Fixture, Errors)) {
    OutError = FString::Join(Errors, TEXT(" | "));
    return false;
  }
  const S09MoveDraftBench::FApplyResult Result =
      S09MoveDraftBench::Apply(Fixture, Snapshot, BoardModel, Fighters, BenchViewerId, CommandUi);
  if (!Result.MismatchId.IsEmpty()) {
    FS08Trace::Write(FString::Printf(TEXT("MS-BENCH mismatch id=%s file=%s (%s)"), *Result.MismatchId, *Fixture.File,
                                     *Result.Error));
  }
  if (!Result.bOk) {
    OutError = Result.Error;
    return false;
  }
  bBenchMoveDraft = true;
  MoveHoverCell = Result.Hover;
  FS08Trace::Write(Result.Summary);
  if (BoardActor) {
    if (CommandUi.IsPendingMovePlace()) {
      BoardActor->SetSelectedFighter(CommandUi.PendingFighterId, CommandUi.PendingCells); // MS-T-12 scene
    } else {
      BoardActor->SetSelectedFighter(CommandUi.SelectedFighterId, CommandUi.ReachableCells);
    }
    FS08Trace::Write(FString::Printf(TEXT("MS-BENCH plates=%d%s"), BoardActor->UsesMovePlates() ? 1 : 0,
                                     BoardActor->UsesMovePlates()
                                         ? TEXT("")
                                         : TEXT(" (no -S08MovePlates or M_UM_MovePlate missing: the old readability ring)")));
  }
  return true;
}

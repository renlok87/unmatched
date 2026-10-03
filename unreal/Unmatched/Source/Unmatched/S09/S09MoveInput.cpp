#include "S09MoveInput.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace {
/** Scoped DraftSource: the MS-DRAFT src= of the operations inside. */
struct FS09SourceScope {
  FS09CommandUi& Ui;
  ES09InputSource Previous;
  FS09SourceScope(FS09CommandUi& InUi, ES09InputSource Source) : Ui(InUi), Previous(InUi.DraftSource) {
    Ui.DraftSource = Source;
  }
  ~FS09SourceScope() { Ui.DraftSource = Previous; }
};

bool S09InTiers(const FS09ReachTiers& Tiers, const FIntPoint& Cell) {
  return Tiers.bValid && (Tiers.BaseTier.Contains(Cell) || Tiers.BoostTier.Contains(Cell));
}

const FS08BoardFighter* S09FighterById(const TArray<FS08BoardFighter>& Fighters, const FString& Id) {
  if (Id.IsEmpty()) return nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id.Equals(Id, ESearchCase::CaseSensitive)) return &Fighter;
  }
  return nullptr;
}
}  // namespace

// ---- keys -------------------------------------------------------------------

FS09InputResult FS09MoveInput::OnKey(ES09MoveKey Key, FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                     const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                     const FS09InputView& View) {
  FS09InputResult Out;
  const bool bDraft = Ui.Mode == ES09CommandMode::ManeuverDraft;
  const bool bIdle = Ui.Mode == ES09CommandMode::None;
  if (!bDraft && !bIdle) return Out; // other modes keep their own bindings
  if (bExhaustionOpen && Key != ES09MoveKey::Enter && Key != ES09MoveKey::Escape) {
    Out.bHandled = true; // MS-S-04 is modal: Enter / Esc (and RMB) only
    return Out;
  }
  FS09SourceScope Scope(Ui, ES09InputSource::Key);
  FString Reason;
  switch (Key) {
    case ES09MoveKey::M:
      Out.bHandled = true;
      if (bDraft) {
        Out.Toast = FS09Reason::Make(TEXT("ms.begin.already")); // B-03
        return Out;
      }
      if (bExhaustionOpen) return Out; // MS-S-04 answers Enter / Esc only
      return BeginRequest(Ui, Snapshot, Fighters, View);

    case ES09MoveKey::Enter:
      if (bExhaustionOpen) {
        // MS-S-04 "Begin anyway": the gate is re-checked at the send.
        bExhaustionOpen = false;
        Out.bHandled = true;
        FS09Reason Key2;
        if (!Ui.CanBeginManeuver(Snapshot, Reason, Key2)) {
          Out.Toast = Key2;
          return Out;
        }
        Out.bBeginManeuver = true;
        return Out;
      }
      if (bDraft && bBoostPanelOpen) {
        // MS-S-08: the card under the arrow cursor (MS-E-97).
        Out.bHandled = true;
        const TArray<FS09BoostCard> Offers = Ui.BoostOffers();
        if (!Offers.IsValidIndex(BoostCursor)) {
          Out.Toast = FS09Reason::Make(TEXT("ms.boost.empty"));
          return Out;
        }
        if (Ui.BoostCardId != Offers[BoostCursor].InstanceId &&
            !Ui.ToggleBoostCard(Offers[BoostCursor].InstanceId, Snapshot, Board, Fighters, Reason)) {
          Out.Toast = Ui.LastReason;
          return Out;
        }
        bBoostPanelOpen = false;
        Out.bSelectionChanged = true;
        return Out;
      }
      if (bDraft) {
        Out.bHandled = true;
        if (Ui.ConfirmManeuver(Snapshot, Board, Fighters, Out.Command, Reason)) {
          Out.bConfirmManeuver = true;
        } else if (Ui.LastReason.IsSet()) {
          Out.Toast = Ui.LastReason; // MS-R-16: NeedBoost / Conflict by key
        } else {
          Out.ToastText = TEXT("confirm rejected: ") + Reason; // never silent
        }
        return Out;
      }
      if (Ui.PreDraft.bSet) {
        Out.bHandled = true; // MS-S-03: Enter begins the maneuver
        return BeginRequest(Ui, Snapshot, Fighters, View);
      }
      return Out;

    case ES09MoveKey::Escape:
      return StepBack(/*bRightMouse=*/false, Ui, Snapshot, Board, Fighters, View);

    case ES09MoveKey::Backspace:
    case ES09MoveKey::CtrlZ:
      if (!bDraft) return Out;
      Out.bHandled = true;
      Out.bSelectionChanged = Ui.Undo(Board, Fighters);
      return Out;

    case ES09MoveKey::Delete:
      if (!bDraft) return Out;
      Out.bHandled = true;
      if (!Ui.SelectedFighterId.IsEmpty() && Ui.MoveIndexOf(Ui.SelectedFighterId) != INDEX_NONE) {
        Ui.ClearMove(Ui.SelectedFighterId, Board, Fighters);
        Out.bSelectionChanged = true;
      }
      return Out;

    case ES09MoveKey::Tab:
    case ES09MoveKey::ShiftTab: {
      if (bIdle && !Ui.CanPreDraftNow(Snapshot)) return Out; // MS-S-01/02 only
      const FString Next = Ui.CycleFighter(Fighters, Key == ES09MoveKey::Tab ? 1 : -1);
      if (Next.IsEmpty()) return Out;
      Out.bHandled = true;
      if (bDraft) {
        if (!Ui.SelectFighter(Next, Snapshot, Board, Fighters)) Out.Toast = Ui.LastReason;
      } else if (!Ui.InspectFighter(Next, Snapshot, Board, Fighters)) {
        Out.Toast = Ui.LastReason;
      }
      Out.bSelectionChanged = true;
      return Out;
    }

    case ES09MoveKey::B:
      if (!bDraft) return Out;
      Out.bHandled = true;
      if (bBoostPanelOpen) {
        bBoostPanelOpen = false;
        return Out;
      }
      if (Ui.BoostOffers().Num() == 0) {
        Out.Toast = FS09Reason::Make(TEXT("ms.boost.empty")); // MS-E-11: empty hand, empty panel
        return Out;
      }
      bBoostPanelOpen = true;
      BoostCursor = FMath::Max(0, Ui.BoostOffers().IndexOfByPredicate(
                                      [&Ui](const FS09BoostCard& Card) { return Card.InstanceId == Ui.BoostCardId; }));
      return Out;

    case ES09MoveKey::Left:
    case ES09MoveKey::Right: {
      // With D open the arrows stay with the discard browser (03 §3.2).
      if (!bDraft || !bBoostPanelOpen || View.bDiscardBrowserOpen) return Out;
      Out.bHandled = true;
      const int32 Count = Ui.BoostOffers().Num();
      if (Count > 0) BoostCursor = (BoostCursor + (Key == ES09MoveKey::Right ? 1 : -1) + Count) % Count;
      return Out;
    }

    case ES09MoveKey::CtrlUp:
    case ES09MoveKey::CtrlDown:
      // MS-E-98: before the discard-browser arrows; MS-E-96: no-op without a toast.
      if (!bDraft) return Out;
      Out.bHandled = true;
      if (!Ui.SelectedFighterId.IsEmpty()) {
        Out.bSelectionChanged =
            Ui.MoveOrder(Ui.SelectedFighterId, Key == ES09MoveKey::CtrlUp ? -1 : 1, Snapshot, Board, Fighters);
      }
      return Out;

    case ES09MoveKey::E:
      if (!bDraft) return Out; // outside the draft E ends the turn (caller)
      Out.bHandled = true;
      Out.Toast = FS09Reason::Make(TEXT("why.draft.open"));
      return Out;
  }
  return Out;
}

FS09InputResult FS09MoveInput::BeginRequest(FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                            const TArray<FS08BoardFighter>& Fighters, const FS09InputView& View) {
  FS09InputResult Out;
  Out.bHandled = true;
  FString Reason;
  FS09Reason Key;
  if (!Ui.CanBeginManeuver(Snapshot, Reason, Key)) {
    Out.Toast = Key;
    return Out;
  }
  if (View.OwnDeckCount == 0) {
    // MS-R-03 / MS-E-43: an empty deck - the draw deals 2 damage to every own fighter.
    bExhaustionOpen = true;
    ExhaustionFighters = Ui.OwnLivingFighters(Fighters);
    Out.Toast = FS09Reason::Make(TEXT("ms.begin.exhaustion")).Arg(TEXT("n"), ExhaustionFighters);
    Out.ToastSeconds = 3600.0f; // modal: stays until Enter / Esc
    return Out;
  }
  Out.bBeginManeuver = true;
  return Out;
}

FS09InputResult FS09MoveInput::StepBack(bool bRightMouse, FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                        const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                        const FS09InputView& View) {
  FS09InputResult Out;
  const bool bDraft = Ui.Mode == ES09CommandMode::ManeuverDraft;
  const bool bIdle = Ui.Mode == ES09CommandMode::None;
  if (!bDraft && !bIdle) return Out;
  Out.bHandled = true;
  FS09SourceScope Scope(Ui, bRightMouse ? ES09InputSource::Click : ES09InputSource::Key);
  // (1) Esc closes D / I first; the draft is untouched (MS-E-98).
  if (!bRightMouse && (View.bDiscardBrowserOpen || View.bInspectorOpen)) {
    Out.bCloseDiscardBrowser = View.bDiscardBrowserOpen;
    Out.bCloseInspector = View.bInspectorOpen;
    return Out;
  }
  // MS-S-04 is modal: Esc / RMB = "Cancel" (nothing was sent).
  if (bExhaustionOpen) {
    bExhaustionOpen = false;
    Out.Toast = FS09Reason::Make(TEXT("ms.btn.cancel"));
    Out.ToastSeconds = 1.5f;
    return Out;
  }
  // (2) MS-S-08 closes.
  if (bBoostPanelOpen) {
    bBoostPanelOpen = false;
    return Out;
  }
  if (bDraft) {
    // (3) MS-S-07 -> MS-S-06.
    if (!Ui.SelectedFighterId.IsEmpty()) {
      Ui.DeselectFighter();
      Out.bSelectionChanged = true;
      return Out;
    }
    if (bRightMouse) return Out; // RMB never resets the draft
    // (4) MS-S-06 with moves: reset (undoable with Backspace); (5) empty: the hint.
    if (Ui.Moves.Num() > 0 || !Ui.BoostCardId.IsEmpty()) {
      Ui.CancelDraft();
      Out.bSelectionChanged = true;
    } else {
      Out.Toast = FS09Reason::Make(TEXT("ms.confirm.zero"));
    }
    return Out;
  }
  // (6) MS-S-03 -> MS-S-02 -> MS-S-01.
  if (Ui.PreDraft.bSet) {
    Ui.ClearPreDraft();
    Out.bSelectionChanged = true;
    return Out;
  }
  if (!Ui.SelectedFighterId.IsEmpty()) {
    Ui.DeselectFighter();
    Out.bSelectionChanged = true;
    return Out;
  }
  // (7) MS-S-00/01/11/13 without a selection: the pause (UI-INP-005) - no
  // pause screen in the client yet (MS-E-99).
  if (!bRightMouse) Out.bPauseUnavailable = true;
  return Out;
}

// ---- pointer ---------------------------------------------------------------

void FS09MoveInput::OnPointerPressed(const FIntPoint& Cell, const FString& FighterId) {
  bPressed = true;
  PressedCell = Cell;
  PressedFighterId = FighterId;
}

FS09InputResult FS09MoveInput::OnPointerReleased(const FIntPoint& Cell, const FString& FighterId, FS09CommandUi& Ui,
                                                 const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                                 const TArray<FS08BoardFighter>& Fighters) {
  FS09InputResult Out;
  if (!bPressed) return Out;
  const bool bSameSpace = Cell.X >= 0 && Cell == PressedCell;
  const bool bSameFighter = !FighterId.IsEmpty() && FighterId == PressedFighterId;
  bPressed = false;
  const FIntPoint DownCell = PressedCell;
  PressedCell = FIntPoint(-1, -1);
  PressedFighterId.Reset();
  if (!bSameSpace && !bSameFighter) {
    Out.bHandled = true; // a drag to another space cancels the click (MS-R-34)
    return Out;
  }
  // The same figure under the press and the release is the same click even
  // when the ray lands on another space behind a tall figure.
  return Click(bSameSpace ? Cell : DownCell, bSameFighter ? FighterId : FString(), Ui, Snapshot, Board, Fighters);
}

FS09InputResult FS09MoveInput::OnRightClick(FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                            const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  bPressed = false;
  return StepBack(/*bRightMouse=*/true, Ui, Snapshot, Board, Fighters, FS09InputView());
}

void FS09MoveInput::OnFocusLost() {
  bPressed = false;
  PressedCell = FIntPoint(-1, -1);
  PressedFighterId.Reset();
  HoverCell = FIntPoint(-1, -1);
}

FS09InputResult FS09MoveInput::Click(const FIntPoint& Cell, const FString& FighterId, FS09CommandUi& Ui,
                                     const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                     const TArray<FS08BoardFighter>& Fighters) {
  FS09InputResult Out;
  const bool bDraft = Ui.Mode == ES09CommandMode::ManeuverDraft;
  const bool bIdle = Ui.Mode == ES09CommandMode::None;
  if (!bDraft && !bIdle) return Out;
  // MS-S-00 / MS-S-13 (not the viewer's action time): the plate only (caller).
  if (bIdle && !Ui.CanPreDraftNow(Snapshot)) return Out;
  if (bExhaustionOpen) {
    Out.bHandled = true; // MS-S-04 is modal
    return Out;
  }
  FS09SourceScope Scope(Ui, ES09InputSource::Click);
  FString Reason;
  const bool bCell = Cell.X >= 0 && Cell.Y >= 0;
  const FS08BoardFighter* Selected = S09FighterById(Fighters, Ui.SelectedFighterId);
  const bool bOwnSpace = Selected && bCell && Selected->X == Cell.X && Selected->Y == Cell.Y;
  // (1) MS-R-71: a space of the selected fighter's tiers wins over the figure on it.
  if (Selected && bCell && (S09InTiers(Ui.SelectedTiers, Cell) || (bDraft && bOwnSpace))) {
    Out.bHandled = true;
    Out.bSelectionChanged = true;
    if (bDraft) {
      const int32 Index = Ui.MoveIndexOf(Selected->Id);
      if (Index != INDEX_NONE && Ui.Moves[Index].DestX == Cell.X && Ui.Moves[Index].DestY == Cell.Y) {
        return Out; // MS-E-83: the same target again - nothing
      }
      if (!Ui.SetDestination(Selected->Id, Cell.X, Cell.Y, Snapshot, Board, Fighters, Reason)) {
        Out.Toast = Ui.LastReason;
        Out.IllegalCell = Cell;
        return Out;
      }
      const int32 After = Ui.MoveIndexOf(Selected->Id);
      if (After != INDEX_NONE && Ui.Moves[After].Status == ES09DraftMoveStatus::NeedBoost) {
        // 03 §3.1: a boost-tier target without a big enough card opens MS-S-08.
        bBoostPanelOpen = Ui.BoostOffers().Num() > 0;
        BoostCursor = 0;
        Out.Toast = Ui.Moves[After].Reason;
      }
      return Out;
    }
    bool bUnchanged = false;
    if (!Ui.SetPreDraft(Selected->Id, Cell.X, Cell.Y, Snapshot, Board, Fighters, bUnchanged)) {
      Out.Toast = Ui.LastReason;
      Out.IllegalCell = Cell;
    } else if (!bUnchanged && Ui.PreDraft.bSet && Ui.PreDraft.Status == ES09DraftMoveStatus::NeedBoost) {
      Out.Toast = FS09Reason::Make(TEXT("why.cell.needs.boost")).Arg(TEXT("n"), Ui.PreDraft.RequiredBoost);
    }
    return Out;
  }
  // (2) an own fighter: the actor hit, else the one standing on the space.
  const FS08BoardFighter* Hit = S09FighterById(Fighters, FighterId);
  if (!Hit && bCell) Hit = FS08BoardModel::FighterAt(Fighters, Cell.X, Cell.Y, FString());
  if (Hit && Hit->OwnerId == Ui.ViewerId) {
    Out.bHandled = true;
    Out.bSelectionChanged = true;
    const bool bOk = bDraft ? Ui.SelectFighter(Hit->Id, Snapshot, Board, Fighters)
                            : Ui.InspectFighter(Hit->Id, Snapshot, Board, Fighters);
    if (!bOk) Out.Toast = Ui.LastReason; // e.g. why.immobilized (MS-R-05)
    return Out;
  }
  if (Hit) {
    // An opponent's fighter: the plate (caller); in the draft also the reason.
    if (bDraft) {
      Out.bHandled = true;
      Out.Toast = FS09Reason::Make(TEXT("why.fighter.not.yours"));
    }
    return Out;
  }
  // (3) a space outside the tiers: CUE-004 + the reason, the target unchanged.
  if (Selected && bCell) {
    Out.bHandled = true;
    FS09DraftMove Probe;
    FS09Reason Why;
    Ui.EvaluateDestination(Selected->Id, Cell.X, Cell.Y, Board, Fighters, Probe, Why);
    Out.Toast = Why.IsSet() ? Why : FS09Reason::Make(TEXT("why.cell.no.path")).Arg(TEXT("cell"), Board.CellLabel(Cell.X, Cell.Y));
    Out.IllegalCell = Cell;
  }
  return Out;
}

void FS09MoveInput::OnSnapshot(const FS09CommandUi& Ui, const FS08Snapshot& Snapshot) {
  if (Ui.Mode != ES09CommandMode::ManeuverDraft) bBoostPanelOpen = false;
  if (Ui.Mode != ES09CommandMode::None || Snapshot.CurrentTurnPlayerId != Ui.ViewerId ||
      Snapshot.Phase == TEXT("GAME_OVER")) {
    bExhaustionOpen = false;
  }
}

// ---- review list -------------------------------------------------------------

const TArray<FS09KeyBinding>& FS09MoveInput::Bindings() {
  static const TArray<FS09KeyBinding> List = {
      {TEXT("LMB (release)"), TEXT("select / target / pre-draft"), TEXT(""), false, false},
      {TEXT("RMB"), TEXT("step back (never resets the draft)"), TEXT(""), false, false},
      {TEXT("M"), TEXT("begin maneuver"), TEXT(""), false, false},
      {TEXT("Enter"), TEXT("begin / begin anyway / pick boost / confirm"), TEXT(""), false, false},
      {TEXT("Esc"), TEXT("step back"), TEXT(""), false, false},
      {TEXT("Backspace"), TEXT("undo"), TEXT(""), false, false},
      {TEXT("Ctrl+Z"), TEXT("undo"), TEXT("Backspace"), true, false},
      {TEXT("Delete"), TEXT("clear the selected fighter's move"), TEXT(""), false, false},
      {TEXT("Tab"), TEXT("next own fighter"), TEXT(""), false, false},
      {TEXT("Shift+Tab"), TEXT("previous own fighter"), TEXT("Tab"), true, false},
      {TEXT("1-9"), TEXT("boost by hand position"), TEXT(""), false, false},
      {TEXT("B"), TEXT("boost panel"), TEXT(""), false, false},
      {TEXT("Left/Right"), TEXT("boost panel cursor"), TEXT(""), false, false},
      {TEXT("Ctrl+Up"), TEXT("move earlier"), TEXT("panel button (MS-T-11)"), true, false},
      {TEXT("Ctrl+Down"), TEXT("move later"), TEXT("panel button (MS-T-11)"), true, false},
      {TEXT("E"), TEXT("end turn (refused in the draft)"), TEXT(""), false, false},
  };
  return List;
}

// ---- -S08Maneuver auto driver -------------------------------------------------

bool FS09MoveInput::AutoManeuverTarget(const FS09CommandUi& Ui, const FS08BoardModel& Board,
                                       const TArray<FS08BoardFighter>& Fighters, FString& OutFighterId,
                                       FIntPoint& OutCell) {
  for (const FS08BoardFighter& Hero : Fighters) {
    if (Hero.OwnerId != Ui.ViewerId || !Hero.bIsHero || !Hero.CanBeMover() || Hero.X < 0 ||
        FS09DraftEval::IsImmobilized(Hero)) {
      continue;
    }
    const FS08ReachMap Reach =
        FS08BoardModel::ComputeReachMap(Board, Fighters, Hero.Id, FS08BoardModel::FighterMovement(Hero));
    for (const FIntPoint& Next : Board.Neighbours(FIntPoint(Hero.X, Hero.Y))) {
      if (Reach.DistanceTo(Next) == 1 && FS08BoardModel::IsReachEndpoint(Fighters, Reach, Next)) {
        OutFighterId = Hero.Id;
        OutCell = Next;
        return true;
      }
    }
    return false; // the hero has no free neighbour (Cobble's opening can box it in)
  }
  return false;
}

bool FS09MoveInput::AutoManeuverSettled(int32 StartSeq, const FS08Snapshot& Snapshot) {
  return Snapshot.SequenceNumber >= StartSeq + 2 && FS08Contracts::PendingManeuverId(Snapshot).IsEmpty();
}

bool FS09MoveInput::LegacyQuickMoveEnabled() {
  return FParse::Param(FCommandLine::Get(), TEXT("S08LegacyQuickMove"));
}

bool FS09MoveInput::RoutesMoveSelection(ES09CommandMode Mode, bool bLegacyQuickMove) {
  return Mode == ES09CommandMode::ManeuverDraft || (Mode == ES09CommandMode::None && !bLegacyQuickMove);
}

bool FS09MoveInput::LegacyQuickMoveReachable(ES09CommandMode Mode, bool bLegacyQuickMove) {
  return bLegacyQuickMove && Mode == ES09CommandMode::None;
}

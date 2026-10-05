#include "S09PendingPresent.h"

#include "Dom/JsonObject.h"

// ---- skipped-effect notes (metadata.skippedEffects, DE-016 -> DE-020) ----

FS09Reason FS09SkippedEffectNote::Why() const {
  // NO_VALID_TARGETS is the only reason the server writes (04 §4.3.1); an unknown one still gets the same
  // explanation instead of silence (a skipped effect never goes unexplained).
  return FS09Reason::Make(TEXT("why.effect.no.targets"));
}

bool FS09SkippedEffectsFeed::Parse(const FS08Snapshot& Snapshot, TArray<FS09SkippedEffectNote>& OutNotes) {
  OutNotes.Reset();
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
  if (!Meta->TryGetArrayField(TEXT("skippedEffects"), Entries) || !Entries) return false;
  for (const TSharedPtr<FJsonValue>& Value : *Entries) {
    const TSharedPtr<FJsonObject>* Entry = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Entry) || !Entry->IsValid()) continue;
    FS09SkippedEffectNote Note;
    double Number = 0.0;
    if (!(*Entry)->TryGetNumberField(TEXT("n"), Number) || !FMath::IsFinite(Number) || Number < 1.0) continue;
    Note.N = static_cast<int32>(FMath::Min(Number, 2147483647.0));
    if ((*Entry)->TryGetNumberField(TEXT("seq"), Number) && FMath::IsFinite(Number)) {
      Note.Seq = static_cast<int32>(FMath::Clamp(Number, -2147483648.0, 2147483647.0));
    }
    (*Entry)->TryGetStringField(TEXT("reason"), Note.Reason);
    (*Entry)->TryGetStringField(TEXT("playerId"), Note.PlayerId);
    (*Entry)->TryGetStringField(TEXT("effectId"), Note.EffectId);
    (*Entry)->TryGetStringField(TEXT("kind"), Note.Kind);
    (*Entry)->TryGetStringField(TEXT("text"), Note.Text);
    OutNotes.Add(MoveTemp(Note));
  }
  OutNotes.Sort([](const FS09SkippedEffectNote& A, const FS09SkippedEffectNote& B) { return A.N < B.N; });
  return true;
}

TArray<FS09SkippedEffectNote> FS09SkippedEffectsFeed::Consume(const FS08Snapshot& Snapshot) {
  TArray<FS09SkippedEffectNote> Out;
  if (!Snapshot.Metadata.IsValid()) return Out;  // a body without metadata says nothing about skips
  TArray<FS09SkippedEffectNote> Notes;
  Parse(Snapshot, Notes);
  if (!bPrimed) {
    bPrimed = true;
    for (const FS09SkippedEffectNote& Note : Notes) LastShownN = FMath::Max(LastShownN, Note.N);
    return Out;
  }
  for (const FS09SkippedEffectNote& Note : Notes) {
    if (Note.N > LastShownN) Out.Add(Note);
  }
  for (const FS09SkippedEffectNote& Note : Out) LastShownN = FMath::Max(LastShownN, Note.N);
  return Out;
}

void FS09SkippedEffectsFeed::Reset() {
  LastShownN = 0;
  bPrimed = false;
}

// ---- presentation of an own head ----

const TCHAR* S09PendingPresentName(ES09PendingPresent Present) {
  switch (Present) {
    case ES09PendingPresent::Compact:
      return TEXT("compact");
    case ES09PendingPresent::Toast:
      return TEXT("toast");
    default:
      return TEXT("modal");
  }
}

FS09PendingVariant FS09PendingVariant::FromCommand(const FS09PendingChoiceCommand& Command) {
  FS09PendingVariant Out;
  Out.OptionIndex = Command.OptionIndex;
  Out.FighterId = Command.FighterId;
  Out.bHasCell = Command.bHasCell;
  Out.CellX = Command.bHasCell ? Command.CellX : -1;
  Out.CellY = Command.bHasCell ? Command.CellY : -1;
  return Out;
}

FString FS09PendingVariant::Describe() const {
  TArray<FString> Parts;
  if (OptionIndex >= 0) Parts.Add(FString::Printf(TEXT("option=%d"), OptionIndex));
  if (!FighterId.IsEmpty()) Parts.Add(TEXT("fighter=") + FighterId);
  if (bHasCell) Parts.Add(FString::Printf(TEXT("cell=%d,%d"), CellX, CellY));
  return Parts.Num() > 0 ? FString::Join(Parts, TEXT(" ")) : FString(TEXT("none"));
}

FString FS09PendingPresenter::Signature(const FS08PendingEffect& Head) {
  return FString::Printf(TEXT("%s|%s|%s|%d"), *Head.Type, *Head.Text.TrimStartAndEnd(), *Head.FighterName,
                         Head.bOptional ? 1 : 0);
}

bool FS09PendingPresenter::Observe(const FS08PendingEffect& Head, int32 TurnCount) {
  if (Head.Id.IsEmpty() || Head.Id == HeadId) return false;
  HeadId = Head.Id;
  HeadSignature = Signature(Head);
  bCollapsed = false;
  FHistory& Entry = History.FindOrAdd(HeadSignature);
  OpensBefore = Entry.Opens;
  // 02-ux-ui-spec §4.6 п. 6 (SD-19): a repeating optional trigger is a toast, not a modal; a mandatory choice
  // that comes back every turn (seen in an earlier turn) is compact. Twice in ONE turn (an EACH effect) stays
  // a modal - that is not "every turn". The first open of anything is the modal.
  if (Entry.Opens > 0 && Head.bOptional) {
    Present = ES09PendingPresent::Toast;
  } else if (Entry.Opens > 0 && Entry.LastTurn != INDEX_NONE && Entry.LastTurn != TurnCount) {
    Present = ES09PendingPresent::Compact;
  } else {
    Present = ES09PendingPresent::Modal;
  }
  Entry.Opens += 1;
  Entry.LastTurn = TurnCount;
  return true;
}

void FS09PendingPresenter::Clear() {
  HeadId.Reset();
  HeadSignature.Reset();
  bCollapsed = false;
  Present = ES09PendingPresent::Modal;
  OpensBefore = 0;
}

void FS09PendingPresenter::Reset() {
  Clear();
  History.Reset();
}

bool FS09PendingPresenter::Collapse() {
  if (!IsOpen() || bCollapsed || Present == ES09PendingPresent::Toast) return false;
  bCollapsed = true;
  return true;
}

bool FS09PendingPresenter::Expand() {
  if (!IsOpen()) return false;
  if (bCollapsed) {
    bCollapsed = false;
    return true;
  }
  if (Present == ES09PendingPresent::Toast) {
    Present = ES09PendingPresent::Modal;  // "details": the full choice
    return true;
  }
  return false;
}

bool FS09PendingPresenter::Toggle() {
  if (!IsOpen()) return false;
  return (bCollapsed || Present == ES09PendingPresent::Toast) ? Expand() : Collapse();
}

void FS09PendingPresenter::Remember(const FS08PendingEffect& Head, const FS09PendingVariant& Variant) {
  if (!Variant.IsSet()) return;
  History.FindOrAdd(Signature(Head)).Last = Variant;
}

const FS09PendingVariant* FS09PendingPresenter::Remembered() const {
  if (!IsOpen()) return nullptr;
  const FHistory* Entry = History.Find(HeadSignature);
  return Entry && Entry->Last.IsSet() ? &Entry->Last : nullptr;
}

FString FS09PendingPresenter::TraceLine() const {
  return FString::Printf(TEXT("MS-PENDING present=%s id=%s opens=%d collapsed=%d"), S09PendingPresentName(Present),
                         *HeadId, OpensBefore, bCollapsed ? 1 : 0);
}

// ---- two steps: object -> target (up to N) ----

const TCHAR* FS09PendingStep::StepName() const {
  return Prompt.Key == FName(TEXT("ms.choice.object")) ? TEXT("object") : TEXT("target");
}

FS09PendingStep S09DescribePendingStep(const FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                       const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  FS09PendingStep Out;
  if (Ui.Mode != ES09CommandMode::PendingChoice || !Ui.bHasPendingChoice) return Out;
  const FS08PendingEffect& Head = Ui.PendingChoice;
  Out.bOpponentTurn = !Snapshot.CurrentTurnPlayerId.IsEmpty() && Snapshot.CurrentTurnPlayerId != Ui.ViewerId;
  if (Head.Type == TEXT("MOVE") || Head.Type == TEXT("PLACE")) {
    const FS09PendingMovePrompt Prompt = Ui.DescribePendingMovePlace(Board, Fighters);
    if (!Prompt.bValid || Prompt.bNoSpace) return Out;  // nothing to pick: S09PendingHasNoTargets explains
    Out.bValid = true;
    Out.Steps = 2;
    if (Prompt.FighterId.IsEmpty()) {
      Out.Step = 1;
      Out.Prompt = FS09Reason::Make(TEXT("ms.choice.object"));
    } else {
      Out.Step = 2;
      Out.N = Prompt.bPlace ? 1 : Prompt.Allowance;
      Out.Prompt = FS09Reason::Make(TEXT("ms.choice.target")).Arg(TEXT("n"), Out.N);
    }
    return Out;
  }
  if (Head.Type == TEXT("TARGET_FIGHTER") || Head.Type == TEXT("CHOOSE_SPACE")) {
    Out.bValid = true;
    Out.Steps = 1;
    Out.Step = 1;
    Out.N = 1;
    Out.Prompt = FS09Reason::Make(TEXT("ms.choice.target")).Arg(TEXT("n"), 1);
  }
  return Out;
}

bool S09PendingHasNoTargets(const FS09CommandUi& Ui, const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                            const TArray<FS08BoardFighter>& Fighters) {
  if (Ui.Mode != ES09CommandMode::PendingChoice || !Ui.bHasPendingChoice) return false;
  const FString& Type = Ui.PendingChoice.Type;
  if (Type == TEXT("MOVE") || Type == TEXT("PLACE")) {
    const FS09PendingMovePrompt Prompt = Ui.DescribePendingMovePlace(Board, Fighters);
    return Prompt.bValid && Prompt.bNoSpace;
  }
  if (Type == TEXT("TARGET_FIGHTER")) {
    TArray<FString> Legal;
    Ui.PendingLegalFighters(Fighters, Legal);
    return Legal.Num() == 0;
  }
  if (Type == TEXT("CHOOSE_SPACE")) {
    return Ui.ComputePendingCells(Snapshot, Board, Fighters).Num() == 0;
  }
  return false;
}

bool S09ApplyPendingVariant(FS09CommandUi& Ui, const FS09PendingVariant& Variant, const FS08Snapshot& Snapshot,
                            const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                            FString& OutApplied) {
  OutApplied.Reset();
  if (Ui.Mode != ES09CommandMode::PendingChoice || !Variant.IsSet()) return false;
  const FString& Type = Ui.PendingChoice.Type;
  FString Reason;
  TArray<FString> Parts;
  if (Type == TEXT("CHOOSE_ONE") && Variant.OptionIndex >= 0) {
    for (int32 I = 0; I < Ui.PendingChoice.Options.Num(); ++I) {
      if (Ui.PendingChoice.Options[I].Index == Variant.OptionIndex && Ui.SelectPendingOption(I, Reason)) {
        Parts.Add(FString::Printf(TEXT("option=%d"), Variant.OptionIndex));
        break;
      }
    }
  }
  if ((Type == TEXT("MOVE") || Type == TEXT("PLACE") || Type == TEXT("TARGET_FIGHTER")) &&
      !Variant.FighterId.IsEmpty() && Ui.SelectPendingFighter(Variant.FighterId, Snapshot, Fighters, Reason)) {
    Parts.Add(TEXT("fighter=") + Variant.FighterId);
  }
  const bool bCellType = Type == TEXT("CHOOSE_SPACE") ||
                         ((Type == TEXT("MOVE") || Type == TEXT("PLACE")) && !Ui.PendingFighterId.IsEmpty());
  if (bCellType && Variant.bHasCell &&
      Ui.SelectPendingCell(Variant.CellX, Variant.CellY, Snapshot, Board, Fighters, Reason)) {
    Parts.Add(FString::Printf(TEXT("cell=%d,%d"), Variant.CellX, Variant.CellY));
  }
  OutApplied = FString::Join(Parts, TEXT(" "));
  return Parts.Num() > 0;
}

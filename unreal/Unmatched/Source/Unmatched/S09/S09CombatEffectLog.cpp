// R-02: the public combat effect log on the client - see S09CombatEffectLog.h.
#include "S09CombatEffectLog.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

namespace {
const TCHAR* const OutcomeOrder[] = {TEXT("APPLIED"), TEXT("CHOICE"), TEXT("MANUAL"), TEXT("NO_TARGETS"),
                                     TEXT("FAILED")};

bool ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32& Out) {
  double Number = 0.0;
  if (!Object->TryGetNumberField(Field, Number) || !FMath::IsFinite(Number)) return false;
  Out = static_cast<int32>(FMath::Clamp(Number, -2147483648.0, 2147483647.0));
  return true;
}

/** What one entry says on its own: the printed sentence, or the effect kind and its value. */
FString EntryText(const FS09CombatEffectEntry& Entry) {
  if (!Entry.Text.IsEmpty()) return Entry.Text;
  return Entry.bHasValue ? FString::Printf(TEXT("%s %d"), *Entry.Kind, Entry.Value) : Entry.Kind;
}
}  // namespace

bool FS09LastCombat::Read(const FS08Snapshot& Snapshot, FS09LastCombat& Out) {
  Out = FS09LastCombat();
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TSharedPtr<FJsonObject>* RecordPtr = nullptr;
  if (!Meta->TryGetObjectField(TEXT("lastCombat"), RecordPtr) || !RecordPtr || !RecordPtr->IsValid()) return false;
  const TSharedPtr<FJsonObject>& Record = *RecordPtr;
  if (!ReadInt(Record, TEXT("seq"), Out.Seq) || !Record->TryGetStringField(TEXT("attackerFighterId"), Out.AttackerFighterId) ||
      !Record->TryGetStringField(TEXT("targetFighterId"), Out.TargetFighterId)) {
    Out = FS09LastCombat();
    return false;
  }
  ReadInt(Record, TEXT("n"), Out.N);
  Record->TryGetStringField(TEXT("attackerPlayerId"), Out.AttackerPlayerId);
  Record->TryGetStringField(TEXT("defenderPlayerId"), Out.DefenderPlayerId);
  ReadInt(Record, TEXT("defenderDamage"), Out.DefenderDamage);
  Record->TryGetBoolField(TEXT("attackerWon"), Out.bAttackerWon);
  Record->TryGetBoolField(TEXT("attackerCardCancelled"), Out.bAttackerCardCancelled);
  const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
  if (!Record->TryGetArrayField(TEXT("appliedEffects"), Values) || !Values) return true;
  for (const TSharedPtr<FJsonValue>& Value : *Values) {
    const TSharedPtr<FJsonObject>* EntryPtr = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(EntryPtr) || !EntryPtr || !EntryPtr->IsValid()) continue;
    const TSharedPtr<FJsonObject>& J = *EntryPtr;
    FS09CombatEffectEntry Entry;
    if (!ReadInt(J, TEXT("i"), Entry.I) || Entry.I < 0) continue;
    J->TryGetStringField(TEXT("timing"), Entry.Timing);
    J->TryGetStringField(TEXT("side"), Entry.Side);
    J->TryGetStringField(TEXT("playerId"), Entry.PlayerId);
    const TSharedPtr<FJsonObject>* Source = nullptr;
    if (J->TryGetObjectField(TEXT("source"), Source) && Source && Source->IsValid()) {
      (*Source)->TryGetStringField(TEXT("name"), Entry.CardName);
      (*Source)->TryGetStringField(TEXT("catalogId"), Entry.CatalogId);
    }
    J->TryGetStringField(TEXT("effectId"), Entry.EffectId);
    J->TryGetStringField(TEXT("kind"), Entry.Kind);
    J->TryGetStringField(TEXT("outcome"), Entry.Outcome);
    Entry.bHasValue = ReadInt(J, TEXT("value"), Entry.Value);
    const TArray<TSharedPtr<FJsonValue>>* Targets = nullptr;
    if (J->TryGetArrayField(TEXT("targets"), Targets) && Targets) {
      for (const TSharedPtr<FJsonValue>& Target : *Targets) {
        FString Id;
        if (Target.IsValid() && Target->TryGetString(Id) && !Id.IsEmpty()) Entry.Targets.Add(Id);
      }
    }
    J->TryGetStringField(TEXT("text"), Entry.Text);
    if (!ReadInt(J, TEXT("parent"), Entry.Parent) || Entry.Parent < 0) Entry.Parent = -1;
    // `hidden` (engine note, non-public refs) is deliberately not decoded: the panel and the trace are the same for
    // the owner and the opponent.
    Out.Entries.Add(MoveTemp(Entry));
  }
  Out.Entries.StableSort([](const FS09CombatEffectEntry& A, const FS09CombatEffectEntry& B) { return A.I < B.I; });
  return true;
}

bool FS09LastCombat::Matches(int32 BaselineSeq, int32 ClosingSeq, const FString& AttackerId,
                             const FString& TargetId) const {
  return Seq > BaselineSeq && Seq <= ClosingSeq && AttackerFighterId == AttackerId && TargetFighterId == TargetId;
}

FString FS09LastCombat::OutcomeCounts() const {
  TArray<FString> Parts;
  for (const TCHAR* Outcome : OutcomeOrder) {
    int32 Count = 0;
    for (const FS09CombatEffectEntry& Entry : Entries) Count += Entry.Outcome == Outcome ? 1 : 0;
    if (Count > 0) Parts.Add(FString::Printf(TEXT("%s:%d"), Outcome, Count));
  }
  int32 Other = 0;
  for (const FS09CombatEffectEntry& Entry : Entries) {
    bool bKnown = false;
    for (const TCHAR* Outcome : OutcomeOrder) bKnown |= Entry.Outcome == Outcome;
    Other += bKnown ? 0 : 1;
  }
  if (Other > 0) Parts.Add(FString::Printf(TEXT("OTHER:%d"), Other));
  return Parts.Num() > 0 ? FString::Join(Parts, TEXT(",")) : FString(TEXT("-"));
}

bool S09CombatEffectLog::IsLineOutcome(const FString& Outcome) {
  return Outcome == TEXT("APPLIED") || Outcome == TEXT("CHOICE") || Outcome == TEXT("MANUAL");
}

TArray<FS09CombatEffectLine> S09CombatEffectLog::Lines(const FS09LastCombat& Log) {
  TArray<FS09CombatEffectLine> Out;
  TMap<int32, int32> LineOfEntry;  // log `i` -> index in Out
  for (const FS09CombatEffectEntry& Entry : Log.Entries) {
    if (!IsLineOutcome(Entry.Outcome)) continue;
    // An option chosen in a CHOOSE_ONE completes its parent's line.
    if (Entry.Parent >= 0) {
      if (const int32* ParentLine = LineOfEntry.Find(Entry.Parent)) {
        Out[*ParentLine].Text += FString::Printf(TEXT(" -> %s"), *EntryText(Entry));
        LineOfEntry.Add(Entry.I, *ParentLine);
        continue;
      }
    }
    FS09CombatEffectLine Line;
    Line.EntryIndex = Entry.I;
    Line.bAttackerSide = Entry.Side != TEXT("DEFENDER");
    Line.CardName = Entry.CardName;
    Line.Text = EntryText(Entry);
    Line.Outcome = Entry.Outcome;
    LineOfEntry.Add(Entry.I, Out.Num());
    Out.Add(MoveTemp(Line));
  }
  return Out;
}

FString S09CombatEffectLog::TraceLine(int32 ClosingSeq, const FS09LastCombat* Log, const TCHAR* Src,
                                      int32 LineCount) {
  return FString::Printf(TEXT("COMBAT-LOG seq=%d log=%s n=%s entries=%d lines=%d src=%s outcomes=%s"), ClosingSeq,
                         Log ? *FString::FromInt(Log->Seq) : TEXT("-"), Log ? *FString::FromInt(Log->N) : TEXT("-"),
                         Log ? Log->Entries.Num() : 0, LineCount, Src, Log ? *Log->OutcomeCounts() : TEXT("-"));
}

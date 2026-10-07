// R-02 (run H, DE-018 tail; 01 F-01; RESEARCH-2026-10-05 findings 5-6): the client side of the public combat effect
// log. The server writes metadata.lastCombat on the snapshot that resolved a combat (R-01, 16-network-contract.md
// §5.1): the fired card effects in the order the server applied them, each with its side, source card, kind,
// outcome, printed text and causal parent (an option chosen in a CHOOSE_ONE points at the CHOOSE_ONE).
// World-free (headless-testable); AS08FlowGameMode::StartCombatStage turns the log into the effect lines of the
// combat staging (FS09CombatStage: +600 ms per line, F-01) and the edge-of-field card panels show them.
//
// Privacy by construction: `hidden` (the engine note and non-public references, sent only to the effect's owner) is
// never decoded, so the owner and the opponent build the same lines from their projections.
//
// What is a line (F-01 "сработавшая строка"): an entry that fired and shows the printed effect - APPLIED, CHOICE (a
// choice the player answered) and MANUAL (printed text the players apply by hand). An option of a CHOOSE_ONE is not
// a line of its own: it completes its parent's line ("-> option"). NO_TARGETS (nothing to hit, the skipped-effect
// note explains it) and FAILED add no line.
//
// Trace: COMBAT-LOG seq=<closing seq> log=<lastCombat.seq|-> n=<n|-> entries=<m> lines=<l> src=<log|none|other>
//        outcomes=<APPLIED:a,CHOICE:c,...|->  (counts only: no card names, no text)
// gated by cue_contract.py check-trace C8 (the staging's lines= equals the log's) and C9 (--min-effect-lines).
#pragma once

#include "CoreMinimal.h"
#include "../S08/S08Contracts.h"

/** One metadata.lastCombat.appliedEffects entry (public part only). */
struct UNMATCHED_API FS09CombatEffectEntry {
  int32 I = -1;          // 0-based order within the combat
  FString Timing;        // IMMEDIATELY | DURING | AFTER
  FString Side;          // ATTACKER | DEFENDER
  FString PlayerId;      // owner of the effect
  FString CardName;      // source.name
  FString CatalogId;     // source.catalogId
  FString EffectId;
  FString Kind;          // EffectType
  FString Outcome;       // APPLIED | CHOICE | NO_TARGETS | MANUAL | FAILED
  bool bHasValue = false;
  int32 Value = 0;
  TArray<FString> Targets;  // fighter and player ids only
  FString Text;          // printed effect sentence (may be empty)
  int32 Parent = -1;     // `i` of the entry that caused this one
};

/** metadata.lastCombat (R-01). */
struct UNMATCHED_API FS09LastCombat {
  int32 N = 0;
  int32 Seq = -1;
  FString AttackerFighterId;
  FString TargetFighterId;
  FString AttackerPlayerId;
  FString DefenderPlayerId;
  int32 DefenderDamage = 0;
  bool bAttackerWon = false;
  bool bAttackerCardCancelled = false;  // AU-S5: the attack card's effects (and its boost) were cancelled
  TArray<FS09CombatEffectEntry> Entries;

  /** Decodes metadata.lastCombat. False when the field is absent or malformed (no seq / fighters) - "no record"
   *  (saves and servers before R-01). Entries without a non-negative `i` are dropped; `hidden` is never read. */
  static bool Read(const FS08Snapshot& Snapshot, FS09LastCombat& Out);
  /** The record belongs to the combat the client closes: it was resolved after the baseline (the last applied
   *  open-combat snapshot) and no later than the closing snapshot, between the same two fighters. */
  bool Matches(int32 BaselineSeq, int32 ClosingSeq, const FString& AttackerId, const FString& TargetId) const;
  /** "APPLIED:2,CHOICE:1" in the fixed outcome order ("-" for an empty log). */
  FString OutcomeCounts() const;
};

/** One effect line of the combat staging (+600 ms, F-01) and of the card panel at the field edge. */
struct UNMATCHED_API FS09CombatEffectLine {
  int32 EntryIndex = -1;   // `i` of the log entry that opened the line
  bool bAttackerSide = true;
  FString CardName;
  FString Text;            // what the panel prints: the printed sentence (+ "-> option"), or kind and value
  FString Outcome;
  bool bPrintedText = false;  // VS-3 HB-33: Text is the printed sentence (not the kind / value fallback)
};

namespace S09CombatEffectLog {
/** True for the outcomes that make a line of their own (APPLIED, CHOICE, MANUAL). */
UNMATCHED_API bool IsLineOutcome(const FString& Outcome);
/** The effect lines of a combat, in the server's order (see the header comment for the rule). */
UNMATCHED_API TArray<FS09CombatEffectLine> Lines(const FS09LastCombat& Log);
/** The COMBAT-LOG trace line. Src: log (the record matched; lines from it), none (no record), other (a record of
 *  another combat: 0 lines). */
UNMATCHED_API FString TraceLine(int32 ClosingSeq, const FS09LastCombat* Log, const TCHAR* Src, int32 LineCount);
}  // namespace S09CombatEffectLog

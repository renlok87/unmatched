// R-02 automation tests: the public combat effect log on the client (S09CombatEffectLog.h) and the effect lines of
// the combat staging (S09CombatStage.h).
//   Unmatched.S09.CombatEffectLog.Parse       - metadata.lastCombat (R-01 shape) -> lines: which outcomes make a
//                                               line, a CHOOSE_ONE option completes its parent's line, the owner's
//                                               and the opponent's projections give the same public lines (hidden is
//                                               never read), the match rule, the COMBAT-LOG trace line;
//   Unmatched.S09.CombatStage.EffectLines     - F-01: 0 / 1 / 2 lines give 3.9 / 4.5 / 5.1 s, each line 600 ms in
//                                               the trace, the panel queries (shown / highlighted), the skip.
#if WITH_AUTOMATION_TESTS

#include "S09CombatEffectLog.h"
#include "S09CombatStage.h"
#include "../S08/S08CueDispatcher.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace S09CombatEffectLogTest {
FS08Snapshot SnapshotWithMeta(const FString& MetaJson) {
  FS08Snapshot Out;
  TSharedPtr<FJsonObject> Meta;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(MetaJson);
  if (FJsonSerializer::Deserialize(Reader, Meta) && Meta.IsValid()) Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Out;
}

/** A combat of seq 42 (Arthur -> Medusa) in the R-01 shape. `bOwnerView`: the attacker's projection (its entries
 *  keep `hidden`); otherwise the defender's (the attacker's `hidden` is cut by filterPrivateData). */
FString LastCombatJson(bool bOwnerView) {
  const FString Hidden = bOwnerView
                             ? TEXT(",\"hidden\":{\"note\":\"SECRET-NOTE found Excalibur\",\"refs\":[\"card-inst-9\"]}")
                             : TEXT("");
  return FString::Printf(
      TEXT("{\"actionsRemaining\":1,\"lastCombat\":{\"n\":3,\"seq\":42,\"attackerFighterId\":\"arthur\","
           "\"targetFighterId\":\"medusa\",\"attackerPlayerId\":\"pA\",\"defenderPlayerId\":\"pD\","
           "\"attackerCardId\":\"c1\",\"finalAttack\":5,\"finalDefense\":3,\"defenderDamage\":2,"
           "\"attackerWon\":true,\"attackerCardCancelled\":false,\"defenderCardCancelled\":false,"
           "\"appliedEffects\":["
           "{\"i\":0,\"timing\":\"DURING\",\"side\":\"ATTACKER\",\"playerId\":\"pA\",\"source\":{\"kind\":\"CARD\","
           "\"cardId\":\"c1\",\"catalogId\":\"cat-feint\",\"name\":\"Feint\"},\"effectId\":\"e0\",\"kind\":"
           "\"CANCEL_EFFECTS\",\"outcome\":\"APPLIED\",\"targets\":[],\"text\":\"Cancel all effects on your "
           "opponent's card.\"%s},"
           "{\"i\":1,\"timing\":\"AFTER\",\"side\":\"DEFENDER\",\"playerId\":\"pD\",\"source\":{\"kind\":\"CARD\","
           "\"cardId\":\"c2\",\"catalogId\":\"cat-gaze\",\"name\":\"Gaze\"},\"effectId\":\"e1\",\"kind\":"
           "\"CHOOSE_ONE\",\"outcome\":\"CHOICE\",\"targets\":[],\"text\":\"Choose one.\"},"
           "{\"i\":2,\"timing\":\"AFTER\",\"side\":\"DEFENDER\",\"playerId\":\"pD\",\"source\":{\"kind\":\"CARD\","
           "\"cardId\":\"c2\",\"catalogId\":\"cat-gaze\",\"name\":\"Gaze\"},\"effectId\":\"e1b\",\"kind\":"
           "\"DRAW_CARDS\",\"outcome\":\"APPLIED\",\"value\":1,\"targets\":[\"pD\"],\"parent\":1},"
           "{\"i\":3,\"timing\":\"AFTER\",\"side\":\"ATTACKER\",\"playerId\":\"pA\",\"source\":{\"kind\":\"CARD\","
           "\"cardId\":\"c1\",\"catalogId\":\"cat-feint\",\"name\":\"Feint\"},\"effectId\":\"e3\",\"kind\":\"MOVE\","
           "\"outcome\":\"NO_TARGETS\",\"targets\":[]},"
           "{\"i\":4,\"timing\":\"AFTER\",\"side\":\"ATTACKER\",\"playerId\":\"pA\",\"source\":{\"kind\":\"CARD\","
           "\"cardId\":\"c1\",\"catalogId\":\"cat-feint\",\"name\":\"Feint\"},\"effectId\":\"e4\",\"kind\":"
           "\"DEAL_DAMAGE\",\"outcome\":\"FAILED\",\"targets\":[]},"
           "{\"i\":5,\"timing\":\"AFTER\",\"side\":\"ATTACKER\",\"playerId\":\"pA\",\"source\":{\"kind\":\"CARD\","
           "\"cardId\":\"c1\",\"catalogId\":\"cat-feint\",\"name\":\"Feint\"},\"effectId\":\"e5\",\"kind\":"
           "\"CUSTOM\",\"outcome\":\"MANUAL\",\"targets\":[\"medusa\"],\"text\":\"Resolve by hand.\"%s}"
           "]}}"),
      *Hidden, *Hidden);
}

FS09CombatStageInput Input(bool bText, int32 Lines) {
  FS09CombatStageInput In;
  In.Seq = 42;
  In.AttackerId = TEXT("arthur");
  In.TargetId = TEXT("medusa");
  In.bHasEffectText = bText;
  In.EffectLines = Lines;
  for (int32 I = 0; I < Lines; ++I) {
    FS09CombatEffectLine Line;
    Line.EntryIndex = I;
    Line.bAttackerSide = I % 2 == 0;
    Line.CardName = TEXT("Feint");
    Line.Text = FString::Printf(TEXT("line %d"), I + 1);
    In.Effects.Add(Line);
  }
  In.Damage = 2;
  In.HpBefore = 7;
  In.HpAfter = 5;
  In.ContactMs = 292;
  In.ContactSource = TEXT("notify");
  In.Reveal.AttackValue = 4;
  In.Reveal.DefenseValue = 0;
  In.Reveal.bNoDefense = true;
  return In;
}

struct FRun {
  FS09CombatStage Stage;
  FS08CueDispatcher Cues;
  TArray<FString> Lines;
  TArray<FS09CombatStageEvent> Events;
};

void RunToEnd(FRun& Run, const FS09CombatStageInput& In, int64 SkipAt = -1) {
  Run.Stage.Start(In, 0, Run.Cues, Run.Lines, Run.Events);
  for (int64 T = 0; T <= 20000 && Run.Stage.IsActive(); ++T) {
    Run.Stage.Tick(T, Run.Cues, Run.Lines, Run.Events);
    Run.Cues.Advance(T, Run.Lines);
    if (T == SkipAt) Run.Stage.Skip(T, TEXT("click"), Run.Cues, Run.Lines, Run.Events);
  }
  Run.Cues.Finish(Run.Lines);
}

TArray<FString> StageLines(const TArray<FString>& Lines, const TCHAR* Stage) {
  TArray<FString> Out;
  const FString Needle = FString::Printf(TEXT(" stage=%s "), Stage);
  for (const FString& L : Lines) {
    if (L.Contains(Needle)) Out.Add(L);
  }
  return Out;
}
}  // namespace S09CombatEffectLogTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatEffectLogParseTest, "Unmatched.S09.CombatEffectLog.Parse",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatEffectLogParseTest::RunTest(const FString&) {
  using namespace S09CombatEffectLogTest;
  FS09LastCombat Owner, Opponent;
  TestTrue("owner view decodes", FS09LastCombat::Read(SnapshotWithMeta(LastCombatJson(true)), Owner));
  TestTrue("opponent view decodes", FS09LastCombat::Read(SnapshotWithMeta(LastCombatJson(false)), Opponent));
  TestEqual("seq", Owner.Seq, 42);
  TestEqual("n", Owner.N, 3);
  TestEqual("six entries", Owner.Entries.Num(), 6);
  TestEqual("damage", Owner.DefenderDamage, 2);
  TestTrue("attacker won", Owner.bAttackerWon);
  TestEqual("parent of the chosen option", Owner.Entries[2].Parent, 1);
  TestTrue("value", Owner.Entries[2].bHasValue && Owner.Entries[2].Value == 1);
  TestEqual("outcome counts", Owner.OutcomeCounts(), FString(TEXT("APPLIED:2,CHOICE:1,MANUAL:1,NO_TARGETS:1,FAILED:1")));

  // Which entries make a line: APPLIED, CHOICE (+ its option), MANUAL; not NO_TARGETS / FAILED.
  const TArray<FS09CombatEffectLine> Lines = S09CombatEffectLog::Lines(Owner);
  TestEqual("three lines", Lines.Num(), 3);
  if (Lines.Num() == 3) {
    TestTrue("line 1 = the attacker's Feint", Lines[0].bAttackerSide && Lines[0].CardName == TEXT("Feint") &&
                                                  Lines[0].Text == TEXT("Cancel all effects on your opponent's card."));
    TestTrue("line 2 = the defender's choice with its option", !Lines[1].bAttackerSide && Lines[1].EntryIndex == 1 &&
                                                                   Lines[1].Text == TEXT("Choose one. -> DRAW_CARDS 1"));
    TestTrue("line 3 = the manual effect", Lines[2].Outcome == TEXT("MANUAL") && Lines[2].EntryIndex == 5);
  }
  TestFalse("NO_TARGETS is no line", S09CombatEffectLog::IsLineOutcome(TEXT("NO_TARGETS")));
  TestFalse("FAILED is no line", S09CombatEffectLog::IsLineOutcome(TEXT("FAILED")));

  // Privacy: both seats print the same public lines; the owner-only note never reaches a line.
  const TArray<FS09CombatEffectLine> OppLines = S09CombatEffectLog::Lines(Opponent);
  TestEqual("same line count on both seats", OppLines.Num(), Lines.Num());
  for (int32 I = 0; I < FMath::Min(Lines.Num(), OppLines.Num()); ++I) {
    TestEqual(FString::Printf(TEXT("line %d identical"), I + 1), OppLines[I].Text, Lines[I].Text);
    TestFalse(FString::Printf(TEXT("line %d has no hidden note"), I + 1), Lines[I].Text.Contains(TEXT("SECRET")));
  }
  const FString Trace = S09CombatEffectLog::TraceLine(43, &Owner, TEXT("log"), Lines.Num());
  TestEqual("trace line", Trace,
            FString(TEXT("COMBAT-LOG seq=43 log=42 n=3 entries=6 lines=3 src=log "
                         "outcomes=APPLIED:2,CHOICE:1,MANUAL:1,NO_TARGETS:1,FAILED:1")));
  TestFalse("trace carries no card name or text", Trace.Contains(TEXT("Feint")) || Trace.Contains(TEXT("SECRET")));
  TestEqual("trace without a record",
            S09CombatEffectLog::TraceLine(43, nullptr, TEXT("none"), 0),
            FString(TEXT("COMBAT-LOG seq=43 log=- n=- entries=0 lines=0 src=none outcomes=-")));

  // The match rule: resolved after the baseline and no later than the closing snapshot, same fighters.
  TestTrue("closing seq", Owner.Matches(40, 42, TEXT("arthur"), TEXT("medusa")));
  TestTrue("merged snapshots: closing seq later", Owner.Matches(40, 44, TEXT("arthur"), TEXT("medusa")));
  TestFalse("record of an earlier combat", Owner.Matches(42, 45, TEXT("arthur"), TEXT("medusa")));
  TestFalse("record after the closing snapshot", Owner.Matches(40, 41, TEXT("arthur"), TEXT("medusa")));
  TestFalse("other fighters", Owner.Matches(40, 42, TEXT("medusa"), TEXT("arthur")));

  // No record / malformed record / empty log.
  FS09LastCombat None;
  TestFalse("no lastCombat", FS09LastCombat::Read(SnapshotWithMeta(TEXT("{\"actionsRemaining\":1}")), None));
  TestFalse("no metadata", FS09LastCombat::Read(FS08Snapshot(), None));
  TestFalse("record without seq",
            FS09LastCombat::Read(SnapshotWithMeta(TEXT("{\"lastCombat\":{\"attackerFighterId\":\"a\","
                                                       "\"targetFighterId\":\"b\"}}")),
                                 None));
  FS09LastCombat Empty;
  TestTrue("empty log decodes",
           FS09LastCombat::Read(SnapshotWithMeta(TEXT("{\"lastCombat\":{\"n\":1,\"seq\":7,\"attackerFighterId\":\"a\","
                                                      "\"targetFighterId\":\"b\",\"appliedEffects\":[]}}")),
                                Empty));
  TestEqual("empty log: no lines", S09CombatEffectLog::Lines(Empty).Num(), 0);
  TestEqual("empty log: outcomes -", Empty.OutcomeCounts(), FString(TEXT("-")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatStageEffectLinesTest, "Unmatched.S09.CombatStage.EffectLines",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatStageEffectLinesTest::RunTest(const FString&) {
  using namespace S09CombatEffectLogTest;
  // F-01: 600 + 800 + 1000 + 600 x lines + 300 + contact 292 + 900.
  const int64 Want[] = {3892, 4492, 5092};
  for (int32 N = 0; N <= 2; ++N) {
    FRun Run;
    RunToEnd(Run, Input(true, N));
    TestEqual(FString::Printf(TEXT("%d lines: total"), N), Run.Stage.TotalMs(), Want[N]);
    const TArray<FString> Effects = StageLines(Run.Lines, TEXT("effect"));
    TestEqual(FString::Printf(TEXT("%d lines: effect trace lines"), N), Effects.Num(), N);
    for (const FString& L : Effects) TestTrue("each line 600 ms", L.Contains(TEXT(" ms=600 skipped=0")));
    TestEqual(FString::Printf(TEXT("%d lines: read 1000"), N), StageLines(Run.Lines, TEXT("read")).Num(), 1);
    bool bStartLines = false;
    for (const FString& L : Run.Lines) {
      bStartLines |= L.Contains(TEXT(" stage=start ")) && L.Contains(FString::Printf(TEXT(" lines=%d "), N));
    }
    TestTrue(FString::Printf(TEXT("%d lines: start line carries lines=%d"), N, N), bStartLines);
  }

  // Panel queries: line k appears with its step (flip 620 + read 1000 = 1620, 2220), highlight 400.
  {
    FS09CombatStage Stage;
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    Stage.Start(Input(true, 2), 0, Cues, Lines, Events);
    TestEqual("in the read: no line", Stage.EffectLinesShown(1619), 0);
    TestEqual("line 1 at 1620", Stage.EffectLinesShown(1620), 1);
    TestEqual("line 1 lit", Stage.HighlightedEffectLine(1620), 0);
    TestEqual("line 1 highlight ends at +400", Stage.HighlightedEffectLine(2020), -1);
    TestEqual("line 2 at 2220", Stage.EffectLinesShown(2220), 2);
    TestEqual("line 2 lit", Stage.HighlightedEffectLine(2300), 1);
    TestEqual("slam at 2820", Stage.GetSlamStartMs(), static_cast<int64>(2820));
    TestEqual("lines stay after the slam", Stage.EffectLinesShown(3000), 2);
  }
  // Speed fast: highlight 200, step 400 (holds are not scaled: 400 x 0.5 + 200).
  {
    FS09CombatStage Stage;
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    FS09CombatStageInput In = Input(true, 1);
    In.SpeedMul = 0.5f;
    Stage.Start(In, 0, Cues, Lines, Events);
    TestEqual("fast: line at 310 + 1000", Stage.EffectLinesShown(1310), 1);
    TestEqual("fast: highlight 200", Stage.HighlightedEffectLine(1510), -1);
    TestEqual("fast: slam after a 400 step", Stage.GetSlamStartMs(), static_cast<int64>(1710));
  }
  // The skip in line 2: line 1 stays, line 2 ends now, every line is on the panel, nothing lit.
  {
    FRun Run;
    RunToEnd(Run, Input(true, 2), /*SkipAt=*/2400);
    const TArray<FString> Effects = StageLines(Run.Lines, TEXT("effect"));
    TestEqual("two effect lines", Effects.Num(), 2);
    if (Effects.Num() == 2) {
      TestTrue("line 1 played", Effects[0].Contains(TEXT(" i=1 ms=600 skipped=0")));
      TestTrue("line 2 cut at the skip", Effects[1].Contains(TEXT(" t=2400 i=2 ms=180 skipped=1")));
    }
    TestEqual("total after the skip", Run.Stage.TotalMs(), static_cast<int64>(600 + 2400 + 180 + 292 + 900));
  }
  {
    FS09CombatStage Stage;
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    Stage.Start(Input(true, 2), 0, Cues, Lines, Events);
    TestTrue("skip in the read", Stage.Skip(1000, TEXT("space"), Cues, Lines, Events));
    TestEqual("all lines on the panel from the skip", Stage.EffectLinesShown(1000), 2);
    TestEqual("nothing lit after the skip", Stage.HighlightedEffectLine(1000), -1);
    TestEqual("slam at the skip", Stage.GetSlamStartMs(), static_cast<int64>(1000));
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

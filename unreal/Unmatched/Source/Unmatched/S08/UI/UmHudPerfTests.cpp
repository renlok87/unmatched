// VS-3 HUD budget meter tests (05-production-plan §3 VS-3; HUD-RULES П8; UmHudPerf.h):
//   Unmatched.S08.Hud.Perf.Meter   the block order (hidden first), the skipped frames after a switch, the pairs of a
//                                  hidden block and the shown block after it, the median of the paired differences,
//                                  the pause of an evidence frame (shown, the block starts over), the trace lines.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Perf" <abs log>
#if WITH_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "UmHudPerf.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPerfMeterTest, "Unmatched.S08.Hud.Perf.Meter",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmHudPerfMeterTest::RunTest(const FString& Parameters) {
  TArray<float> Twenty;
  for (int32 I = 20; I >= 1; --I) Twenty.Add(static_cast<float>(I));
  TestEqual(TEXT("quantile p95 of 1..20"), UmHudPerf::Quantile(Twenty, 0.95f), 19.0f);
  TestEqual(TEXT("median even"), UmHudPerf::Median(TArray<float>{4.0f, 1.0f, 3.0f, 2.0f}), 2.5f);
  TestEqual(TEXT("median none"), UmHudPerf::Median(TArray<float>()), 0.0f);

  FUmHudPerfMeter M;
  M.BlockFrames = 10;
  M.SkipFrames = 2;
  TArray<FString> Lines;
  // the first block is hidden: the meter asks for the HUD hidden until the block ends
  bool bShow = true;
  int32 Frames = 0;
  // hidden blocks: GT 1.0 (a 9.0 spike in a skipped frame must not count), GPU 2.0; shown blocks: GT 1.2, GPU 2.1
  for (int32 Pair = 0; Pair < 12; ++Pair) {
    for (int32 Half = 0; Half < 2; ++Half) {
      for (int32 F = 0; F < 10; ++F) {
        const bool bShownBlock = Half == 1;
        const float Gt = F == 0 ? 9.0f : (bShownBlock ? 1.2f : 1.0f);
        bShow = M.Step(Gt, bShownBlock ? 2.1f : 2.0f, false, Lines);
        ++Frames;
        if (F < 9) TestEqual(*FString::Printf(TEXT("visibility inside block %d/%d frame %d"), Pair, Half, F), bShow, bShownBlock);
      }
    }
  }
  TestEqual(TEXT("frames"), Frames, 240);
  TestEqual(TEXT("pairs"), M.Pairs(), 12);
  TestTrue(TEXT("median dGT p95 ~ 0.2"), FMath::IsNearlyEqual(M.MedianDeltaGtP95(), 0.2f, 1.0e-4f));
  TestTrue(TEXT("median dGPU p95 ~ 0.1"), FMath::IsNearlyEqual(M.MedianDeltaGpuP95(), 0.1f, 1.0e-4f));
  int32 PeriodLines = 0, SummaryLines = 0;
  for (const FString& L : Lines) {
    PeriodLines += L.StartsWith(TEXT("HUDPERF period=")) ? 1 : 0;
    SummaryLines += L.StartsWith(TEXT("HUDPERF summary why=every-10 pairs=10 ")) ? 1 : 0;
  }
  TestEqual(TEXT("one line per block"), PeriodLines, 24);
  TestEqual(TEXT("a summary after 10 pairs"), SummaryLines, 1);
  TestTrue(TEXT("first block hidden"), Lines.Num() > 0 && Lines[0].StartsWith(TEXT("HUDPERF period=0 shown=0 frames=8 ")));
  const FString Sum = M.Summary(TEXT("end"));
  TestTrue(TEXT("summary fields"), Sum.Contains(TEXT("pairs=12 dGtP95Med=0.200")) && Sum.Contains(TEXT("dGpuP95Med=0.100")) &&
                                       Sum.Contains(TEXT("budgetGt=0.5 budgetGpu=0.3")));

  // a pause (an evidence frame in flight) shows the HUD and restarts the hidden block; no pair is made across it
  FUmHudPerfMeter P;
  P.BlockFrames = 10;
  P.SkipFrames = 2;
  TArray<FString> PL;
  for (int32 F = 0; F < 5; ++F) P.Step(1.0f, 1.0f, false, PL);
  TestTrue(TEXT("pause shows the HUD"), P.Step(1.0f, 1.0f, true, PL));
  TestEqual(TEXT("still the hidden block"), P.Period(), 0);
  TestFalse(TEXT("hidden again after the pause"), P.Step(1.0f, 1.0f, false, PL));
  for (int32 F = 0; F < 9; ++F) P.Step(1.0f, 1.0f, false, PL);
  TestEqual(TEXT("hidden block finished after a full block"), P.Period(), 1);
  TestTrue(TEXT("its line has 8 samples"), PL.Num() == 1 && PL[0].StartsWith(TEXT("HUDPERF period=0 shown=0 frames=8 ")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

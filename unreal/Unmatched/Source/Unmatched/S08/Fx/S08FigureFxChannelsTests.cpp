// FX-06 / FX-17 / FX-19 (Z-2 review fix 1): the figure channels at the card's time stamps, driven through the channel
// code itself (FS08FigureFxChannels: Start* + Advance with the world clock in seconds), not through the bare curves.
// The Z-2 build passed seconds where the channels took milliseconds (the hit flash and rim lived one frame, the
// defense rim never showed); the bare-curve tests and the static bench frames could not see it - this test does.
#include "S08FigureFxChannels.h"

#if WITH_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FigureFxChannelTimingTest,
    "Unmatched.S08.HeroesV2.FxChannelTiming the hit / defense / hover channels at the card time stamps, ms not s (FX-06/17/19)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FigureFxChannelTimingTest::RunTest(const FString&) {
  using namespace S08FigureFx;
  // the presets are milliseconds (the cards' numbers)
  TestEqual("HitFlashMs 70", HitFlashMs, 70.0);
  TestEqual("HitRim 300 ms from C+70", HitRim.TotalMs + HitRim.DelayMs, 370.0);
  TestEqual("DefenseRim t0 = event + 150", DefenseRim.DelayMs, 150.0);
  TestEqual("HoverRim in 150", HoverRim.InMs, 150.0);
  TestEqual("HoverLeaveMs 120", HoverLeaveMs, 120.0);

  // FX-19: the hit at C = 12.5 s of the world clock (a non-zero clock: a seconds/ms mix-up cannot hide)
  {
    FS08FigureFxChannels Ch;
    const double C = 12.5;
    Ch.StartHit(C, /*bDamage=*/true, /*bReduced=*/false);
    TestTrue("hit C+0: animating", Ch.Advance(C));
    TestEqual("hit C+0: flash 1", Ch.GetFlash(), 1.0f);
    TestEqual("hit C+0: rim 0 (waits for the flash)", Ch.GetRim(), 0.0f);
    Ch.Advance(C + 0.035);
    TestEqual("hit C+35: flash 1", Ch.GetFlash(), 1.0f);
    TestEqual("hit C+35: rim 0", Ch.GetRim(), 0.0f);
    Ch.Advance(C + 0.070);
    TestEqual("hit C+70: flash 0 (one frame)", Ch.GetFlash(), 0.0f);
    TestEqual("hit C+70: rim 1 (hard start)", Ch.GetRim(), 1.0f);
    TestEqual("hit rim width 0.35", Ch.GetRimWidth(), 0.35f);
    Ch.Advance(C + 0.200);
    TestEqual("hit C+200: flash 0", Ch.GetFlash(), 0.0f);
    TestEqual("hit C+200: rim 1", Ch.GetRim(), 1.0f);
    Ch.Advance(C + 0.320);
    TestEqual("hit C+320: rim half way out", Ch.GetRim(), 0.5f, 0.001f);
    TestFalse("hit C+370: done", Ch.Advance(C + 0.370));
    TestEqual("hit C+370: rim 0", Ch.GetRim(), 0.0f);
  }
  // FX-23 / FX-19: damage 0 - the rim alone
  {
    FS08FigureFxChannels Ch;
    Ch.StartHit(3.0, /*bDamage=*/false, false);
    Ch.Advance(3.035);
    TestEqual("damage 0 C+35: no flash", Ch.GetFlash(), 0.0f);
    Ch.Advance(3.2);
    TestEqual("damage 0 C+200: rim 1", Ch.GetRim(), 1.0f);
  }
  // FX-19 reduced motion: no flash, the rim 0.6 for 100 ms
  {
    FS08FigureFxChannels Ch;
    Ch.StartHit(7.0, true, /*bReduced=*/true);
    Ch.Advance(7.035);
    TestEqual("reduced hit: no flash", Ch.GetFlash(), 0.0f);
    TestEqual("reduced hit C+35: rim 0.6", Ch.GetRim(), 0.6f);
    Ch.Advance(7.1);
    TestEqual("reduced hit C+100: rim 0", Ch.GetRim(), 0.0f);
  }
  // FX-17: the defense from the event E; t0 = E+150: +60 the peak, held to +180, 0 at +300
  {
    FS08FigureFxChannels Ch;
    const double E = 40.0;
    Ch.StartRim(E, DefenseRim, false);
    Ch.Advance(E + 0.100);
    TestEqual("defense E+100 (before t0): rim 0", Ch.GetRim(), 0.0f);
    Ch.Advance(E + 0.150 + 0.030);
    TestEqual("defense t0+30: ease-out 0.75", Ch.GetRim(), 0.75f, 0.001f);
    Ch.Advance(E + 0.150 + 0.060);
    TestEqual("defense t0+60: peak 1", Ch.GetRim(), 1.0f);
    TestEqual("VC C3 ВР-VC-16: defense width 0.6 (wider than the hit rim)", Ch.GetRimWidth(), 0.6f);
    Ch.Advance(E + 0.150 + 0.180);
    TestEqual("defense t0+180: still 1", Ch.GetRim(), 1.0f);
    Ch.Advance(E + 0.150 + 0.240);
    TestEqual("defense t0+240: half way out", Ch.GetRim(), 0.5f, 0.001f);
    TestFalse("defense t0+300: done", Ch.Advance(E + 0.150 + 0.300));
    TestEqual("defense t0+300: rim 0", Ch.GetRim(), 0.0f);
    // reduced motion: 0.6 for 100 ms from t0
    FS08FigureFxChannels R;
    R.StartRim(E, DefenseRim, true);
    R.Advance(E + 0.150 + 0.050);
    TestEqual("reduced defense t0+50: 0.6", R.GetRim(), 0.6f);
    R.Advance(E + 0.150 + 0.100);
    TestEqual("reduced defense t0+100: 0", R.GetRim(), 0.0f);
  }
  // FX-06: the hover - in over 150 ms (ease-out to 0.6), held, out over 120 ms
  {
    FS08FigureFxChannels Ch;
    const double H = 5.0;
    Ch.StartRim(H, HoverRim, false);
    Ch.Advance(H + 0.075);
    TestEqual("hover +75: ease-out 0.45", Ch.GetRim(), 0.45f, 0.001f);
    TestEqual("hover width 0.2", Ch.GetRimWidth(), 0.2f);
    Ch.Advance(H + 0.150);
    TestEqual("hover +150: 0.6", Ch.GetRim(), 0.6f);
    TestFalse("hover held: the timer may stop", Ch.Advance(H + 2.0));
    TestEqual("hover +2 s: still 0.6", Ch.GetRim(), 0.6f);
    Ch.LeaveRim(H + 2.0, HoverLeaveMs, false);
    Ch.Advance(H + 2.060);
    TestEqual("leave +60: 0.3", Ch.GetRim(), 0.3f, 0.001f);
    TestFalse("leave +120: done", Ch.Advance(H + 2.120));
    TestEqual("leave +120: 0", Ch.GetRim(), 0.0f);
    // reduced motion (keep): 0.6 at once, 0 at once
    FS08FigureFxChannels R;
    R.StartRim(H, HoverRim, true);
    R.Advance(H);
    TestEqual("reduced hover: 0.6 at once", R.GetRim(), 0.6f);
    R.LeaveRim(H + 1.0, HoverLeaveMs, true);
    R.Advance(H + 1.0);
    TestEqual("reduced hover leave: 0 at once", R.GetRim(), 0.0f);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

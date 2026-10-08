// VS-6 F4 FX-34 / FX-35 / FX-36 (S08CuePostProcess.h), world-free:
//   Unmatched.S08.CuePostProcess.Curve    - FX-34 keyframes: 0 -> 1 in 500 ms ease-in-out (G0+250 = 0.5), reduced 100;
//                                            FX-36 return 1 -> 0 linear in 300 ms (R0+200 = 1/3, ВР-VS5-SC33-02)
//   Unmatched.S08.CuePostProcess.Compose  - victory 7100 K (warm), defeat 5700 K (cold) x 0.8 (ВР-VS6-44), vignette 0.4 + 0.25, desat x 0.64 (frame S -30 %), both
//                                            x 0.8 x 0.64; inactive at rest (the component is off)
//   Unmatched.S08.CuePostProcess.State    - one grade per game over, D5 duplicate loss, the return, a loss during the
//                                            return, the bench weights
//   Unmatched.S08.CuePostProcess.NetWatch - the HB-14 chip's edges: the match start is not a loss, lost / recovered,
//                                            a snapshot applied while lost is the recovered state, leaving resets
//   Unmatched.S08.CuePostProcess.Spawner  - the spawner refuses the seqs <= R after the reconnect, a new match clears it
#include "S08CuePostProcess.h"
#include "S08CueFxSpawner.h"
#include "../UI/UmConnectionBadge.h"

#if WITH_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CuePostProcessCurveTest, "Unmatched.S08.CuePostProcess.Curve",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CuePostProcessCurveTest::RunTest(const FString&) {
  using namespace S08CuePostProcess;
  TestEqual("before the start", OutcomeWeight(990, 1000, 500), 0.0f);
  TestEqual("G0", OutcomeWeight(1000, 1000, 500), 0.0f);
  TestTrue("G0+250 = 0.5 (ease-in-out)", FMath::IsNearlyEqual(OutcomeWeight(1250, 1000, 500), 0.5f, 1e-4f));
  TestTrue("G0+100 eases in (< linear 0.2)", OutcomeWeight(1100, 1000, 500) < 0.2f);
  TestEqual("G0+500 full", OutcomeWeight(1500, 1000, 500), 1.0f);
  TestEqual("held", OutcomeWeight(99999, 1000, 500), 1.0f);
  TestEqual("reduced: full at +100", OutcomeWeight(1100, 1000, ReducedMaxMs), 1.0f);
  TestEqual("no start", OutcomeWeight(5000, -1, 500), 0.0f);
  TestEqual("R0", RestoreWeight(2000, 2000, RestoreMs), 1.0f);
  TestTrue("R0+200 = 1/3 (SC-33 exit frame)", FMath::IsNearlyEqual(RestoreWeight(2200, 2000, RestoreMs), 1.0f / 3.0f, 1e-4f));
  TestEqual("R0+300 back", RestoreWeight(2300, 2000, RestoreMs), 0.0f);
  TestTrue("one frame (16.7 ms) before R0+300 still > 0", RestoreWeight(2283, 2000, RestoreMs) > 0.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CuePostProcessComposeTest, "Unmatched.S08.CuePostProcess.Compose",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CuePostProcessComposeTest::RunTest(const FString&) {
  using namespace S08CuePostProcess;
  const FSettings Rest = Compose(ES08Outcome::None, 1.0f, 0.0f);
  TestFalse("at rest the component is off", Rest.bActive);
  TestEqual("rest white temp", Rest.WhiteTemp, BaseWhiteTemp);
  const FSettings V = Compose(ES08Outcome::Victory, 1.0f, 0.0f);
  TestEqual("victory 7100 K (a warmer frame)", V.WhiteTemp, 7100.0f);
  TestEqual("victory keeps the saturation", V.Saturation, 1.0f);
  TestTrue("vignette = base 0.4 + 0.25", FMath::IsNearlyEqual(V.Vignette, 0.65f, 1e-5f));
  const FSettings D = Compose(ES08Outcome::Defeat, 1.0f, 0.0f);
  TestEqual("defeat 5700 K (a colder frame)", D.WhiteTemp, 5700.0f);
  TestTrue("defeat x 0.8", FMath::IsNearlyEqual(D.Saturation, 0.8f, 1e-5f));
  const FSettings Half = Compose(ES08Outcome::Defeat, 0.5f, 0.0f);
  TestTrue("half way 6100 K", FMath::IsNearlyEqual(Half.WhiteTemp, 6100.0f, 0.01f));
  TestTrue("half way x 0.9", FMath::IsNearlyEqual(Half.Saturation, 0.9f, 1e-5f));
  TestTrue("half way vignette 0.525", FMath::IsNearlyEqual(Half.Vignette, 0.525f, 1e-5f));
  const FSettings L = Compose(ES08Outcome::None, 0.0f, 1.0f);
  TestTrue("lost: active", L.bActive);
  TestTrue("lost x 0.64 (ВР-VS6-43)", FMath::IsNearlyEqual(L.Saturation, 0.64f, 1e-5f));
  TestEqual("lost: no white balance change", L.WhiteTemp, BaseWhiteTemp);
  TestTrue("lost: base vignette (no darkening)", FMath::IsNearlyEqual(L.Vignette, BaseVignette, 1e-5f));
  const FSettings DL = Compose(ES08Outcome::Defeat, 1.0f, 1.0f);
  TestTrue("defeat + lost x 0.8 x 0.64", FMath::IsNearlyEqual(DL.Saturation, 0.512f, 1e-5f));
  const FSettings VL = Compose(ES08Outcome::Victory, 1.0f, 1.0f);
  TestTrue("victory + lost x 0.64", FMath::IsNearlyEqual(VL.Saturation, 0.64f, 1e-5f));
  TestEqual("no outcome ignores its weight", Compose(ES08Outcome::None, 1.0f, 0.0f).Vignette, BaseVignette);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CuePostProcessStateTest, "Unmatched.S08.CuePostProcess.State",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CuePostProcessStateTest::RunTest(const FString&) {
  FS08CuePostProcessState S;
  FString Line;
  TestFalse("no outcome: nothing", S.StartOutcome(ES08Outcome::None, 100, false, TEXT("gone"), TEXT("f"), Line));
  TestTrue("grade starts", S.StartOutcome(ES08Outcome::Defeat, 3125, false, TEXT("gone"), TEXT("f-0-hero"), Line));
  TestEqual("grade line", Line,
            FString(TEXT("FX grade outcome=defeat t=3125 ms=500 reduced=0 src=gone fighter=f-0-hero")));
  TestFalse("one grade per game over", S.StartOutcome(ES08Outcome::Victory, 4000, false, TEXT("result"), TEXT(""), Line));
  TestTrue("G0+500 full (x 0.8)", FMath::IsNearlyEqual(S.Evaluate(3625).Saturation, 0.8f, 1e-5f));
  TestTrue("lost", S.Disconnect(5000, Line));
  TestEqual("desat line", Line, FString(TEXT("FX desat on t=5000 sat=0.64 grade=defeat")));
  TestTrue("weight 1 in the frame of the loss", FMath::IsNearlyEqual(S.Evaluate(5000).Saturation, 0.512f, 1e-5f));
  TestFalse("D5: a repeated loss is a duplicate", S.Disconnect(5100, Line));
  TestEqual("duplicate line", Line, FString(TEXT("FX desat duplicate t=5100")));
  TestTrue("back", S.Reconnect(6000, false, 14, Line));
  TestEqual("return line", Line, FString(TEXT("FX desat off t=6000 ms=300 recovered_seq=14")));
  TestFalse("one return", S.Reconnect(6010, false, 14, Line));
  TestTrue("R0+150 half way", FMath::IsNearlyEqual(S.DisconnectWeight(6150), 0.5f, 1e-4f));
  TestTrue("R0+300 the colour is back (defeat grade stays)", FMath::IsNearlyEqual(S.Evaluate(6300).Saturation, 0.8f, 1e-5f));
  TestTrue("a loss during a return: full weight again", S.Disconnect(6100, Line));
  TestEqual("full again", S.DisconnectWeight(6100), 1.0f);
  TestTrue("reduced return", S.Reconnect(7000, true, 15, Line));
  TestEqual("reduced line", Line, FString(TEXT("FX desat off t=7000 ms=100 recovered_seq=15")));
  TestEqual("reduced: back at +100", S.DisconnectWeight(7100), 0.0f);
  FS08CuePostProcessState R;
  TestTrue("reduced grade", R.StartOutcome(ES08Outcome::Victory, 0, true, TEXT("result"), TEXT(""), Line));
  TestEqual("reduced grade line", Line, FString(TEXT("FX grade outcome=victory t=0 ms=100 reduced=1 src=result fighter=-")));
  TestEqual("reduced: full at +100", R.OutcomeWeightAt(100), 1.0f);
  FS08CuePostProcessState B;
  B.Outcome = ES08Outcome::Victory;
  B.OutcomeStartMs = 0;
  B.BenchOutcomeW = 0.0f;
  TestFalse("bench w 0 = the frame before the grade", B.Evaluate(100000).bActive);
  B.BenchDisconnectW = 1.0f / 3.0f;
  TestTrue("bench desat 1/3 = s 0.88", FMath::IsNearlyEqual(B.Evaluate(0).Saturation, 0.88f, 1e-5f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CuePostProcessNetWatchTest, "Unmatched.S08.CuePostProcess.NetWatch",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CuePostProcessNetWatchTest::RunTest(const FString&) {
  FS08NetWatch W;
  auto In = [](bool bStarted, bool bReady, bool bAwaiting) {
    FS08NetWatchInput I;
    I.bStarted = bStarted;
    I.bStreamReady = bReady;
    I.bAwaitingRecovery = bAwaiting;
    return I;
  };
  // the HB-14 chip on the same inputs (UmConnection::Resolve): lost exactly when the watch reports the loss
  auto Chip = [](bool bReady, bool bWasReady, bool bRecovering) {
    FUmConnInput C;
    C.bStreamReady = bReady;
    C.bWasReady = bWasReady;
    C.bRecovering = bRecovering;
    return UmConnection::Resolve(C);
  };
  TestTrue("match start subscribing: not a loss (chip syncing)", W.Tick(In(true, false, false)) == ES08NetEvent::None);
  TestTrue("chip at the start", Chip(false, false, false) == EUmConnState::Syncing);
  TestTrue("ready", W.Tick(In(true, true, false)) == ES08NetEvent::None);
  TestTrue("the stream drops: lost", W.Tick(In(true, false, false)) == ES08NetEvent::Lost);
  TestTrue("chip lost on the same frame", Chip(false, true, false) == EUmConnState::Lost);
  TestTrue("still down", W.Tick(In(true, false, false)) == ES08NetEvent::None);
  TestFalse("a merge while lost is not the recovered state", W.OnApplied(false));
  TestTrue("the snapshot applied while lost = the recovered state", W.OnApplied(true));
  TestTrue("fed", W.bReconnectFed);
  TestTrue("ready but the state recovery pending: not yet", W.Tick(In(true, true, true)) == ES08NetEvent::None);
  TestTrue("chip syncing meanwhile", Chip(true, true, true) == EUmConnState::Syncing);
  TestTrue("recovered", W.Tick(In(true, true, false)) == ES08NetEvent::Recovered);
  TestTrue("chip online", Chip(true, true, false) == EUmConnState::Online);
  TestFalse("a snapshot on the live stream is not a recovery", W.OnApplied(true));
  TestTrue("second loss", W.Tick(In(true, false, false)) == ES08NetEvent::Lost);
  TestFalse("a new loss feeds again", W.bReconnectFed);
  TestTrue("back without a new snapshot", W.Tick(In(true, true, false)) == ES08NetEvent::Recovered);
  TestTrue("leaving the match", W.Tick(In(false, false, false)) == ES08NetEvent::None);
  TestFalse("reset", W.bSeenReady || W.bLost);
  TestTrue("the next match start is syncing again", W.Tick(In(true, false, false)) == ES08NetEvent::None);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CuePostProcessSpawnerTest, "Unmatched.S08.CuePostProcess.Spawner",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CuePostProcessSpawnerTest::RunTest(const FString&) {
  US08CueFxSpawnerComponent* Spawner = NewObject<US08CueFxSpawnerComponent>();
  TestFalse("nothing stale before a reconnect", Spawner->IsStaleSeq(3));
  TestEqual("no live systems", Spawner->CutAllForReconnect(14), 0);
  TestTrue("seq 12 stale", Spawner->IsStaleSeq(12));
  TestTrue("seq 14 stale", Spawner->IsStaleSeq(14));
  TestFalse("seq 15 shows", Spawner->IsStaleSeq(15));
  TestFalse("no seq: a local show", Spawner->IsStaleSeq(-1));
  Spawner->CutAllForReconnect(10);
  TestEqual("R never moves back", Spawner->GetRecoveredSeq(), 14);
  Spawner->ClearReconnect();
  TestFalse("a new match", Spawner->IsStaleSeq(12));
  return true;
}

#endif

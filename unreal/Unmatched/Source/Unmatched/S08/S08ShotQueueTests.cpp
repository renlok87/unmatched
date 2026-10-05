// I-03 evidence-shot queue (S08ShotQueue.h; defect D-1 of run H): the model without a world.
//   OnePerFrame  two shots asked in one frame: the first leaves, the second waits for a later frame and keeps its name;
//   Busy         nothing leaves while a capture is still in flight (requested or not yet saved);
//   Order        three shots of one frame plus a later one come out FIFO, one per frame;
//   RunH         the run H frame 530 pair (s09-damage-number, then s09-combat-resolve-window) - both names come out.
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.ShotQueue; Quit" -unattended -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ShotQueue.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ShotQueueOnePerFrameTest, "Unmatched.S08.ShotQueue.OnePerFrame",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08ShotQueueOnePerFrameTest::RunTest(const FString& Parameters) {
  FS08ShotQueue Q;
  TestTrue(TEXT("first shot of the frame leaves at once"), Q.Admit(TEXT("a.png"), 10, false));
  TestTrue(TEXT("frame 10 has issued"), Q.IssuedThisFrame(10));
  TestFalse(TEXT("second shot of the same frame is queued"), Q.Admit(TEXT("b.png"), 10, false));
  TestEqual(TEXT("one waiting"), Q.Num(), 1);
  FS08ShotQueue::FEntry E;
  TestFalse(TEXT("no second request in frame 10"), Q.PopReady(10, false, E));
  TestTrue(TEXT("frame 11 lets it out"), Q.PopReady(11, false, E));
  TestEqual(TEXT("its own name"), E.Path, FString(TEXT("b.png")));
  TestEqual(TEXT("queued in frame 10"), E.QueuedFrame, static_cast<uint64>(10));
  TestEqual(TEXT("queue empty"), Q.Num(), 0);
  TestFalse(TEXT("a shot asked after the drain in frame 11 waits"), Q.Admit(TEXT("c.png"), 11, false));
  TestTrue(TEXT("frame 12 lets it out"), Q.PopReady(12, false, E));
  TestEqual(TEXT("c.png"), E.Path, FString(TEXT("c.png")));
  TestTrue(TEXT("free frame, empty queue: at once"), Q.Admit(TEXT("d.png"), 20, false));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ShotQueueBusyTest, "Unmatched.S08.ShotQueue.Busy",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08ShotQueueBusyTest::RunTest(const FString& Parameters) {
  FS08ShotQueue Q;
  TestFalse(TEXT("capture in flight: queued even as the first of the frame"), Q.Admit(TEXT("a.png"), 5, true));
  TestFalse(TEXT("queued shot did not count as this frame's request"), Q.IssuedThisFrame(5));
  FS08ShotQueue::FEntry E;
  TestFalse(TEXT("frame 6 still busy (capture slipped a frame)"), Q.PopReady(6, true, E));
  TestFalse(TEXT("frame 7 still busy"), Q.PopReady(7, true, E));
  TestEqual(TEXT("still waiting"), Q.Num(), 1);
  TestTrue(TEXT("frame 8 idle: out"), Q.PopReady(8, false, E));
  TestEqual(TEXT("a.png"), E.Path, FString(TEXT("a.png")));
  TestFalse(TEXT("empty queue pops nothing"), Q.PopReady(9, false, E));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ShotQueueOrderTest, "Unmatched.S08.ShotQueue.Order",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08ShotQueueOrderTest::RunTest(const FString& Parameters) {
  FS08ShotQueue Q;
  TArray<FString> Issued;
  auto Ask = [&](const TCHAR* Path, uint64 Frame, bool bBusy) {
    if (Q.Admit(Path, Frame, bBusy)) Issued.Add(Path);
  };
  // frame 100: three shots; frame 101: one more (engine idle, but older shots wait - FIFO)
  Ask(TEXT("1.png"), 100, false);
  Ask(TEXT("2.png"), 100, false);
  Ask(TEXT("3.png"), 100, false);
  FS08ShotQueue::FEntry E;
  // 1.png is captured during frame 100's draw, so frame 101 starts idle; the game mode drains first, then gameplay asks
  if (Q.PopReady(101, false, E)) Issued.Add(E.Path);
  Ask(TEXT("4.png"), 101, false);
  for (uint64 Frame = 102; Frame < 110; ++Frame) {
    if (Q.PopReady(Frame, false, E)) Issued.Add(E.Path);
  }
  TestEqual(TEXT("FIFO order, every name once"), FString::Join(Issued, TEXT(",")),
            FString(TEXT("1.png,2.png,3.png,4.png")));
  TestEqual(TEXT("queue empty"), Q.Num(), 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ShotQueueRunHTest, "Unmatched.S08.ShotQueue.RunH",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08ShotQueueRunHTest::RunTest(const FString& Parameters) {
  // Run H, Sarpedon first attempt: both shots asked in frame 530; before I-03 the second replaced the first.
  FS08ShotQueue Q;
  TArray<TPair<uint64, FString>> Requests;  // (frame, path) of every FScreenshotRequest that really left
  if (Q.Admit(TEXT("s09-damage-number.png"), 530, false)) Requests.Add({530, TEXT("s09-damage-number.png")});
  if (Q.Admit(TEXT("s09-combat-resolve-window.png"), 530, false)) {
    Requests.Add({530, TEXT("s09-combat-resolve-window.png")});
  }
  FS08ShotQueue::FEntry E;
  for (uint64 Frame = 531; Frame < 535; ++Frame) {
    if (Q.PopReady(Frame, false, E)) Requests.Add({Frame, E.Path});
  }
  TestEqual(TEXT("two requests"), Requests.Num(), 2);
  if (Requests.Num() == 2) {
    TestEqual(TEXT("damage number first, frame 530"), Requests[0].Value, FString(TEXT("s09-damage-number.png")));
    TestEqual(TEXT("frame 530"), Requests[0].Key, static_cast<uint64>(530));
    TestEqual(TEXT("resolve window next"), Requests[1].Value, FString(TEXT("s09-combat-resolve-window.png")));
    TestEqual(TEXT("frame 531"), Requests[1].Key, static_cast<uint64>(531));
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
